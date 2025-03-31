import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import matplotlib.colors as mcolors

import serial
import threading
from collections import defaultdict

import time
import numpy as np
import signal

stop_thread = threading.Event()

PORT = 'COM5'
BAUDRATE = 115200  

HIDE_LOGGER = True
HIDE_TMR = True
HIDE_IDLE = True

NUM_CORES = 2

# Global variables to store task data
latest_time = [0,0]  # To track the latest time point - format [rpi_time, python_time]

core_activity_data = [defaultdict(lambda: {"times": [], "status": []}) for _ in range(NUM_CORES)]
server_budget_data = defaultdict(lambda: {"times": [], "budget": []})

def read_serial_data():
    global latest_time
    prev_task_name = [None for _ in range(NUM_CORES)]

    try:
        ser = serial.Serial(PORT, BAUDRATE, timeout=1)
    except serial.SerialException as e:
        print(f"Error: {e}")
        return
    
    while not stop_thread.is_set():
        if ser.in_waiting > 0:
            line = ser.readline().decode("utf-8").strip()
            
            if line.startswith("A"): 
                task_name, time_of_switch, core_num = line.split(",")[1:]
                core_idx = int(core_num)
                
                core_activity_data[core_idx][task_name]["times"].append(int(time_of_switch))
                core_activity_data[core_idx][task_name]["status"].append(1)

                if prev_task_name[core_idx] and prev_task_name[core_idx] != task_name:
                    core_activity_data[core_idx][prev_task_name[core_idx]]["times"].append(int(time_of_switch))
                    core_activity_data[core_idx][prev_task_name[core_idx]]["status"].append(0)
                
                prev_task_name[core_idx] = task_name
                
                latest_time[0] = int(time_of_switch)
                latest_time[1] = int(time.time()*1000.0)

            if line.startswith("B"): 
                server_name, timestamp, core_num, budget_remaining = line.split(",")[1:]
                server_budget_data[server_name]["times"].append(int(timestamp))
                server_budget_data[server_name]["budget"].append(int(budget_remaining))

COLOR_LIST = list(mcolors.TABLEAU_COLORS.values())
task_colors = {}

def get_task_color(task):
    if task not in task_colors:
        task_colors[task] = COLOR_LIST[len(task_colors) % len(COLOR_LIST)]
    return task_colors[task]

serial_thread = threading.Thread(target=read_serial_data, daemon=True)
serial_thread.start()

fig, axes = plt.subplots(NUM_CORES + 1, 1, sharex=True, figsize=(8, 8))
axes = axes if isinstance(axes, np.ndarray) else [axes]

def init_plot():
    for ax in axes:
        ax.clear()
    for core_idx in range(NUM_CORES):
        axes[core_idx].set_title(f"Core {core_idx} Task Activity")
        axes[core_idx].set_ylabel("Tasks")
    axes[-1].set_title("Server Budget Activity")
    axes[-1].set_ylabel("Budget Remaining")
    axes[-1].set_xlabel("Time (ms)")
    return []

def update_plot(frame):

    current_time = latest_time[0] + int(time.time() * 1000.0) - latest_time[1]
    
    for core_idx in range(NUM_CORES):
        ax = axes[core_idx]
        ax.clear()
        ax.set_title(f"Core {core_idx} Task Activity")
        ax.set_ylabel("Tasks")

        visible_tasks = [task for task in core_activity_data[core_idx] ]

        if HIDE_LOGGER:
            visible_tasks = [task for task in visible_tasks if task != "Logger"]
        
        if HIDE_TMR:
            visible_tasks = [task for task in visible_tasks if task != "Tmr Svc"]

        if HIDE_IDLE:
            visible_tasks = [task for task in visible_tasks if task != "IDLE1"]
            visible_tasks = [task for task in visible_tasks if task != "IDLE0"]

        visible_tasks = [task for task in visible_tasks if task != "HIDE"]
        
        for idx, task in enumerate(visible_tasks):  # Iterate over task names
            data = core_activity_data[core_idx][task]  # Get the data dictionary

            times = data["times"]
            status = data["status"]
            if times and status:
                task_color = get_task_color(task)
                ax.step(times, [s + 2 * idx for s in status], where="post", label=task, linewidth=2, color=task_color)
                ax.step([times[-1], current_time], [status[-1] + 2 * idx] * 2, where="post", linestyle="dashed", alpha=0.6, color=task_color)
        
        ax.set_xlim(current_time - SHOW_PERIOD_MS, current_time)

        if ax.get_legend_handles_labels()[0]:
            ax.legend(loc="upper left")
    
    budget_ax = axes[-1]
    budget_ax.clear()
    budget_ax.set_title("Server Budget Activity")
    budget_ax.set_ylabel("Budget Remaining")

    # Assign each server a unique index
    server_list = sorted(server_budget_data.keys())  # Keep ordering consistent
    server_indices = {server: idx for idx, server in enumerate(server_list)}

    for server, data in server_budget_data.items():
        times = data["times"]
        budget = data["budget"]
        if times and budget:
            color = get_task_color(server)
            y_offset = server_indices[server] * 500  # Offset each server line (adjust scale as needed)

            # Plot the actual recorded budget data
            budget_ax.plot(times, [b + y_offset for b in budget], linestyle="-", marker="o", label=server, linewidth=2, color=color)

            # Extend the last budget value to the current time with a dashed line
            budget_ax.plot([times[-1], current_time], [budget[-1] + y_offset] * 2, linestyle="dashed", alpha=0.6, color=color)

    # Adjust y-ticks to show server names
    budget_ax.set_yticks([server_indices[s] * 500 for s in server_list])
    budget_ax.set_yticklabels(server_list)

    budget_ax.set_xlim(current_time - SHOW_PERIOD_MS, current_time)

    if budget_ax.get_legend_handles_labels()[0]:
        budget_ax.legend(loc="upper left")

    axes[-1].set_xlabel("Time (ms)")
    return []

def ctrl_c_signal_handler(sig, frame):
    print("Exiting...")
    stop_thread.set()
    plt.close()

signal.signal(signal.SIGINT, ctrl_c_signal_handler)
SHOW_PERIOD_MS = 10_000
ani = FuncAnimation(fig, update_plot, init_func=init_plot, interval=50)
plt.show()
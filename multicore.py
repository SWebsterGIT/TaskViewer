import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import matplotlib.colors as mcolors

import serial
import threading
from collections import defaultdict

import time
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

def read_serial_data():
    global latest_time
    prev_task_name = [None for _ in range(NUM_CORES)]

    try:
        ser = serial.Serial(PORT, BAUDRATE, timeout=1)
    except serial.SerialException as e:
        print(f"Error: {e}")
        
    
    while not stop_thread.is_set():

        # Get a line from the serial input
        if ser.in_waiting > 0:
            line = ser.readline().decode("utf-8").strip()
            

            if line.startswith("A"): # Check the agreed magic number at the start of the line
                    

                    task_name, time_of_switch, core_num = line.split(",")[1:]

                    core_idx = int(core_num)

                    core_activity_data[core_idx][task_name]["times"].append(int(time_of_switch))
                    core_activity_data[core_idx][task_name]["status"].append(1)

                    if prev_task_name[core_idx]:
                        core_activity_data[core_idx][prev_task_name[core_idx]]["times"].append(int(time_of_switch))
                        core_activity_data[core_idx][prev_task_name[core_idx]]["status"].append(0)
                    
                    prev_task_name[core_idx] = task_name
                    
                    latest_time[0] = int(time_of_switch)
                    latest_time[1] = int(time.time()*1000.0)

            if line.startswith("B"): # Check the agreed magic number at the start of the line
                    pass # use CBS version of the script if you expect to display budgets



# Define a fixed set of colors to cycle through
COLOR_LIST = list(mcolors.TABLEAU_COLORS.values())  # You can replace this with any set of colors
task_colors = {}  # Dictionary to store assigned colors

def get_task_color(task):
    """Assigns a color to a task if it doesn't have one already."""
    if task not in task_colors:
        task_colors[task] = COLOR_LIST[len(task_colors) % len(COLOR_LIST)]
    return task_colors[task]



# Start the serial data reading thread
serial_thread = threading.Thread(target=read_serial_data, daemon=True)
serial_thread.start()

# Real-time visualization setup
fig, axes = plt.subplots(NUM_CORES, 1, sharex=True, figsize=(8, 6))  # One plot per core

if NUM_CORES == 1:
    axes = [axes]  # Ensure axes is always a list

def init_plot():
    for core_idx in range(NUM_CORES):
        ax = axes[core_idx]
        ax.clear()
        ax.set_title(f"Core {core_idx} Task Activity")
        ax.set_ylabel("Tasks")

        axes[-1].set_xlabel("Time (ms)")
    return []

def update_plot(frame):

    if not core_activity_data:
        return

    for core_idx in range(NUM_CORES):
        ax = axes[core_idx]
        ax.clear()
        ax.set_title(f"Core {core_idx} Task Activity")
        ax.set_ylabel("Tasks")

        current_time = latest_time[0] + int(time.time() * 1000.0) - latest_time[1]

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

                # Plot the actual recorded data
                ax.step(times, [s + 2 * idx for s in status], where="post", label=task, linewidth=2, color=task_color)

                # Extend the most recent value to the current time
                ax.step([times[-1], current_time], [status[-1] + 2 * idx] * 2, where="post", linestyle="dashed", alpha=0.6,color=task_color)

        # Set the time window to show the last `SHOW_PERIOD_MS` milliseconds
        ax.set_xlim(current_time - SHOW_PERIOD_MS, current_time)
        
        if ax.get_legend_handles_labels()[0]:

            ax.legend(loc="upper left")

        axes[-1].set_xlabel("Time (ms)")

    return []


def ctrl_c_signal_handler(sig, frame):
    print("Exiting...")
    stop_thread.set()
    plt.close()

signal.signal(signal.SIGINT, ctrl_c_signal_handler)  # Capture Ctrl+C to exit so we don't get trapped

# Animate the plot using a callback
SHOW_PERIOD_MS = 10_000
ani = FuncAnimation(fig, update_plot, init_func=init_plot, interval=30)

plt.show() # this blocks and lets the animation do its thing so the program won't end unless stopped externally

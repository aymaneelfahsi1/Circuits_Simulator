import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import numpy as np
import math
import logging

logging.basicConfig(
    level=logging.DEBUG,
    filename='circuit_simulator.log',
    filemode='w',
    format='%(asctime)s - %(levelname)s - %(message)s'
)

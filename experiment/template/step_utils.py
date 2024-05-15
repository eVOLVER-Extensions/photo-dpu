# These are functions used in the custom_script.py file to control a stepped evolution experiment
from custom_script import EXP_NAME
from eVOLVER import EvolverNamespace
import numpy as np
import logging
import os.path
import pandas as pd
from scipy.stats import linregress

#### GENERAL HELPER FUNCTIONS ####

def get_last_n_lines(var_name, vial, n_lines):
    """
    Retrieves the last line of the file for a given variable name and vial number.
    Args:
        var_name (str): The name of the variable.
        vial (int): The vial number.
        n_lines (int): The number of lines to retrieve.
    Returns:
        tuple or numpy.ndarray: Returns the last n lines of the file.
    """
    # Construct file name and path
    file_name = f"vial{vial}_{var_name}.txt"
    if var_name == "gr":
        var_name = "growthrate"
    file_path = os.path.join( EXP_NAME, f'{var_name}', file_name)
    
    try:
        file = EvolverNamespace.tail_to_np(file_path, n_lines)[0] # get last n lines
        return file[-n_lines:]
    except Exception as e:
        print(f"Unable to read file using tail_to_np: {file_path}.\n\tError: {e}")
        # Reading the file directly using numpy
        data = np.genfromtxt(file_path, delimiter=',', skip_header=0)  # Adjust delimiter as necessary
        return data[-n_lines:]

def compare_configs(var_name, vial, current_config):
    """
    Compare the current configuration with the last configuration for a given variable and vial.
    Args:
        var_name (str): The name of the variable.
        vial (int): The name of the vial.
        current_config (list): The current configuration.
    Returns:
        bool: True if the current configuration is different from the last configuration, False otherwise.
    """
    last_config = get_last_n_lines(var_name+'_config', vial, 1)[0] # get last configuration and path
    file_name = f"vial{vial}_{var_name}_config.txt"
    if var_name == "gr":
        var_name = "growthrate"
    config_path = os.path.join( EXP_NAME, f'{var_name}', file_name)
    # Check if config has changed
    if not np.array_equal(last_config[1:], current_config[1:]): # ignore the times, see if arrays are the same
        # Write the updated configuration to the config file
        with open(config_path, "a+") as text_file:
            line = ','.join(str(config) for config in current_config) # Convert the list to a string with commas as separators
            text_file.write(line+'\n') # Write the string to the file, including a newline character
        return True # If the arrays are not the same, return True
    else:
        return False # If the arrays are the same, return False


#### MATH FUNCTIONS ####
def exponential_growth(x, a, b):
    """
    Exponential growth model function.
    
    Args:
    x (array-like): The independent variable where the data is measured (time or equivalent).
    a (float): Initial amount.
    b (float): Growth rate coefficient.
    
    Returns:
    array-like: Computed exponential growth values.
    """
    return a * np.exp(b * x)


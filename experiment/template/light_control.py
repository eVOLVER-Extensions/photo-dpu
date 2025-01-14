import os
import numpy as np
import pandas as pd
import step_utils as su

def control(eVOLVER, vials, elapsed_time, logger, EXP_NAME):
    """
    Controls the light settings for a specific vial based on the elapsed time
    and logs the configuration changes.

    Parameters:
    - eVOLVER: EvolverNamespace object, interface to eVOLVER hardware.
    - elapsed_time: Time since the experiment started.
    - vials: The vial numbers to control.
    - light_cal: Calibration data for converting light to PWM values.
    - logger: Logger object for logging events.
    """
    light_MESSAGE = ['--'] * 32 # initializes light message
    light_cal = eVOLVER.get_light_calibration() # read from calibration file

    for vial in vials:
        light_uE,light_status = determine_light_uE(elapsed_time, vial) # logic to determine light_uE based off of time
        light_pwm = calculate_pwm(light_uE, light_cal[vial])

        log_light_update(eVOLVER, vial, elapsed_time, light_uE, light_pwm, light_status, logger, EXP_NAME)
        light_MESSAGE[vial] = str(light_pwm)

    eVOLVER.update_light(light_MESSAGE)

def determine_light_uE(elapsed_time, vial):
    """
    Determines the light value in uE for the given vial based on elapsed time.

    Parameters:
    - elapsed_time: Time (in hours) since the start of the experiment.
    - vial: The vial identifier to fetch light config and log data.

    Returns:
    - The light value in uE (micromoles per second per meter squared).
    """
    # Load light_config for this vial
    light_config = su.labeled_last_n_lines('light_config', vial, 1).to_dict(orient='records')[0]
    
    ### light_time necessary for more complicated control
    # Load light_log
    # # Calculate how long it has been since the last light update
    # last_light_time = light_log['light_time']
    # light_time = elapsed_time - last_light_time

    # During the acclimation phase
    if elapsed_time < light_config['acclimation_time']:
        return light_config['acclimation_light'], 'ACCLIMATING'
    
    # Post-acclimation phase, determine the light based on ON/OFF cycles
    cycle_start = light_config['cycle_start']  # Time to begin light cycling
    final_light = light_config['final_light']  # Final light intensity after acclimation        
    if elapsed_time >= cycle_start:
        on_length = light_config['ON_length']      # Duration of light being ON in hours
        off_length = light_config['OFF_length']    # Duration of light being OFF in hours

        # Calculate current cycle position based on the elapsed time since cycle_start
        cycle_duration = on_length + off_length    # Total duration of one light cycle (ON + OFF)
        time_in_cycle = (elapsed_time - cycle_start) % cycle_duration  # Position in the current cycle

        # Determine if the current time is in the ON or OFF phase
        if time_in_cycle < on_length:
            # Light is ON
            return final_light, 'CYCLING-ON'
        else:
            # Light is OFF
            return 0, 'CYCLING-OFF'  # Light intensity is 0 when OFF
        
    else:
        return light_config['final_light'], 'ON'


def calculate_pwm(light_uE, calibration):
    """
    Converts a light value (uE) to a PWM value based on calibration data.
    
    Parameters:
    - light_uE: The desired light intensity in uE.

    Returns:
    - light_pwm: The corresponding PWM value for the light intensity.
    """
    if light_uE == 0:
        return 0
    return int((float(light_uE) - calibration[1]) / calibration[0])


def log_light_update(eVOLVER, vial, elapsed_time, light_uE, light_pwm, light_status, logger, expt_name):
    """
    Logs the update of light values to the console, logger, and the log file.

    Parameters:
    - vial: The vial number.
    - elapsed_time: Time since the experiment started.
    - light_uE: The new light value in uE.
    - light_pwm: The new light value in PWM units.
    - logger: Logger object for logging events.
    """
    
    # Load the most recent light_log entry for this vial
    light_log = su.labeled_last_n_lines('light_log', vial, 1).to_dict(orient='records')[0]
    last_light1_uE = light_log['light1_uE']

    if light_uE != last_light1_uE:
        light_time = 0 # Reset light time

        # Log the light update to the log file
        file_name =  f"vial{vial}_light_log.txt"
        file_path = os.path.join(eVOLVER.exp_dir, expt_name, 'light_log', file_name)
        text_file = open(file_path, "a+")
        text_file.write(f"{elapsed_time},{light_time},{light_uE},{light_pwm},0,0,0,0\n") # Format: [elapsed_time, step_changed_time, current_step, current_conc]
        text_file.close()

        # Log the update message to console and file
        message = f"Vial {vial}: LIGHT {light_status} {light_uE}uE, PWM={light_pwm}"
        print(message)
        logger.info(message)

import os
import numpy as np
import pandas as pd
import logging
import utils.file_utils as fu
import step_control

### Light Settings ###
LIGHT_CAL_FILE = 'light_cal.txt'
SAVE_PATH = os.path.dirname(os.path.realpath(__file__))
LIGHT_CAL_PATH = os.path.join(SAVE_PATH, LIGHT_CAL_FILE) # TODO: port light calibration import into light_control.py

class LightController:
    def __init__(self, vials, dilution_window, elapsed_time, eVOLVER):
        self.vials = vials
        self.dilution_window = dilution_window
        self.elapsed_time = elapsed_time
        self.eVOLVER = eVOLVER
        self.logger = eVOLVER.logger
        self.exp_dir = eVOLVER.exp_dir
     
        self.light_MESSAGE = ['--'] * 48 # initializes light message
        self.light_cal = self.get_light_calibration() # read from calibration file

    def control(self):
        """
        Controls the light settings for a specific vial based on the elapsed time
        and logs the configuration changes.
        """
        for vial in self.vials:
            light_uE,light_status_message = self.determine_light_level(vial)

            if light_status_message is not None:
                print(f'{self.elapsed_time}hrs | Vial {vial}: {light_status_message}')
                light_pwm = self.calculate_pwm(light_uE, self.light_cal[vial])
                self.light_MESSAGE[vial] = str(light_pwm)
                
                # Log the light status message
                if light_status_message != '[STEP CHANGE]': # light status message was already logged in light_controller.control()
                    log_message = f"{self.elapsed_time},{light_uE},0,{light_status_message}"
                    fu.update_log(vial, f'light_log', self.elapsed_time, log_message, self.exp_dir)
        
        # Send light command to eVOLVER
        if self.light_MESSAGE != ['--'] * 48:
            self.update_light(self.light_MESSAGE)

    def determine_light_level(self, vial):
        """
        Determines the light value in uE for the given vial based on elapsed time.

        Returns:
        - The light value in uE (micromoles per second per meter squared).
        """
        # Load light_controls for this vial
        light_controls = fu.labeled_last_n_lines('light-control', vial, 1, self.exp_dir).iloc[0]
        step_type = light_controls['step_type'].lower()
        acclimation_time = float(light_controls['acclimation_time'])
        acclimation_light = float(light_controls['acclimation_light'])
        final_light = float(light_controls['final_light'])

        light_log = fu.labeled_last_n_lines('light_log', vial, 1, self.exp_dir).iloc[0]
        current_light = float(light_log['current_step'])

        # During the acclimation phase
        if (self.elapsed_time < acclimation_time) and (current_light != acclimation_light):
            print(f'Vial {vial}: light is ON, acclimating at {acclimation_light}uE')
            return acclimation_light, f'[ACCLIMATING] at {acclimation_light}uE'
        
        # Final light level, no stepped control
        elif (step_type == 'off') and (current_light != final_light):
            print(f'Vial {vial}: light is ON, final light is {final_light}uE')
            return float(light_controls['final_light']), f'[FINAL LIGHT] at {final_light}uE'
        
        # Stepped Control
        else:
            light_controller = step_control.SteppedController(vial, 'light', self.dilution_window, self.elapsed_time, self.eVOLVER)
            MESSAGE,light_status_message= light_controller.control()
            light_log = fu.labeled_last_n_lines('light_log', vial, 1, self.exp_dir).iloc[0]
            current_light = float(light_log['current_step'])

            if light_status_message:
                print(f'Vial {vial}: light updated to {current_light}')
                return current_light,'[STEP CHANGE]'
            
        return None,None

    def calculate_pwm(self, light_uE, calibration):
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

    def get_light_calibration(self):
        file_path = os.path.join(SAVE_PATH, LIGHT_CAL_FILE)
        light_calibration = np.loadtxt(file_path, delimiter="\t")
        if len(light_calibration) == 16:
            light_vals = light_calibration
        else:
            light_vals = light_calibration[0,:]
        return light_vals

    def update_light(self, light_vals, immediate = False):
        data = {'param': 'light', 'value': light_vals,
                'immediate': immediate, 'recurring': True}
        self.logger.debug('light command: %s' % data)
        print(f'TODO implement light command: {data}')
        # self.eVOLVER.emit('command', data, namespace = '/dpu-evolver')

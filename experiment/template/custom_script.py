#!/usr/bin/env python3

import numpy as np
import logging
import os.path
import time
import step_utils as su
import pandas as pd

# logger setup
logger = logging.getLogger(__name__)

##### USER DEFINED GENERAL SETTINGS #####

# If using the GUI for data visualization, do not change EXP_NAME!
# only change if you wish to have multiple data folders within a single
# directory for a set of scripts
EXP_NAME = 'data'

# Port for the eVOLVER connection. You should not need to change this unless you have multiple applications on a single RPi.
EVOLVER_PORT = 8081

##### Identify pump calibration files, define initial values for temperature, stirring, volume, power settings

TEMP_INITIAL = [37] * 16 #degrees C, makes 16-value list
#Alternatively enter 16-value list to set different values
#TEMP_INITIAL = [30,30,30,30,32,32,32,32,34,34,34,34,36,36,36,36]

STIR_INITIAL = [11] * 16 #try 8,10,12 etc; makes 16-value list
#Alternatively enter 16-value list to set different values
#STIR_INITIAL = [7,7,7,7,8,8,8,8,9,9,9,9,10,10,10,10]

VOLUME =  25 #mL, determined by vial cap straw length
OPERATION_MODE = 'turbidostat' #use to choose between 'turbidostat' and 'chemostat' functions
# if using a different mode, name your function as the OPERATION_MODE variable

### Light Settings ###
LIGHT_INITIAL = [100] * 16 #[0,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0] # light values in uE
LIGHT_INITIAL += [0] * 16 # Currently unused second light channel
LIGHT_FINAL = [1000]*16 + [0]*16 # light to set to after TIME_TO_FINAL
# LIGHT_FINAL = [100]*4 + [200]*4 + [300]*4 + [500]*4 + [0] * 16 # light to set to after TIME_TO_FINAL
TIME_TO_FINAL = 4 # hours until setting light to final 
LIGHT_CAL_FILE = 'light_cal.txt'

##### END OF USER DEFINED GENERAL SETTINGS #####


def turbidostat(eVOLVER, input_data, vials, elapsed_time):
    OD_data = input_data['transformed']['od']

    ##### USER DEFINED VARIABLES #####

    ### Turbidostat Settings ###
    turbidostat_vials = vials #vials is all 16, can set to different range (ex. [0,1,2,3]) to only trigger tstat on those vials
    stop_after_n_curves = np.inf #set to np.inf to never stop, or integer value to stop diluting after certain number of growth curves
    OD_values_to_average = 6  # Number of values to calculate the OD average

    lower_thresh = [1.6] * len(vials) #to set all vials to the same value, creates 16-value list
    upper_thresh = [2] * len(vials) #to set all vials to the same value, creates 16-value list

    if eVOLVER.experiment_params is not None:
        lower_thresh = list(map(lambda x: x['lower'], eVOLVER.experiment_params['vial_configuration']))
        upper_thresh = list(map(lambda x: x['upper'], eVOLVER.experiment_params['vial_configuration']))

    #Alternatively, use 16 value list to set different thresholds, use 9999 for vials not being used
    #lower_thresh = [0.2, 0.2, 0.3, 0.3, 9999, 9999, 9999, 9999, 9999, 9999, 9999, 9999, 9999, 9999, 9999, 9999]
    #upper_thresh = [0.4, 0.4, 0.4, 0.4, 9999, 9999, 9999, 9999, 9999, 9999, 9999, 9999, 9999, 9999, 9999, 9999]
    ### End of Turbidostat Settings ###

    ### Stepped Evolution Settings ###
    ## Selection Step Settings ##
    selection_steps = {} # all of the selection value steps to take in this part of the evolution, from low to high
    # Format: {turbidostat_vial1: [step1, step2, ...], turbidostat_vial2: [step1, step2, ...], ...}
    # Manual setting example: {0: [0,0.1,0.2,0.3,...], 1: [0,0.2,0.4,0.6,...], ...}
    # Can be set automatically using below settings

    # Used to calculate steps in selection variable
    generate_steps = True # True if you want to automatically calculate steps; False if you want to manually input each step
    log_steps = False # True if you want logarithmic steps; False if linear
    # For the below settings, specify individually by writing a list of values for each vial, ie [20,20,20,20, 10,10,10,10, 5,5,5,5, 1,1,1,1]
    # selection_stock_conc = [3000,3000,0,0, 3000,3000,3000,3000, 3000,3000,3000,100, 100,100,100,100]  # stock concentrations for each vial; should be low enough that minimum selection level is possible given min_bolus_s
    selection_stock_concs = [3000]*2 + [0]*2 + [3000]*7 + [100]*5 # stock concentrations for each vial; should be low enough that minimum selection level is possible given min_bolus_s
    max_selections = [25]*2 + [0]*2 + [750]*7 + [25]*5 # maximum value your selection can go to; for chemical selection = proportion of stock concentration (don't want to use all of stock)
    min_selections = [25]*2 + [0]*2 + [25]*7 + [1]*5 # minimum value your selection can go to
    selection_step_nums = [20] * len(turbidostat_vials) # number of steps between min_selection and max_selection

    ## Experiment Settings ##
    curves_to_wait = 0 # number of growth curves to wait before starting selection; allows us to calculate WT growth rate
    max_growthrate = 0.1 # growth rate under no selection
    min_growthrate = 0.05 # lowest growth rate allowable for selection; if growth rate is less than this, selection pressure will be eased
    min_step_time = 2 # hours; minimum time to spend on a step before increasing or decreasing selection
    growth_stalled_time = 4 # if growth rate measurement is stalled for this many hours, selection pressure will be eased
    rescue_dilutions = True # True to decrease selection chemical concentration to rescue cells by diluting if selection is too harsh (up to half their original OD)
                            # False to allow to equilibrate to lower selection concentration over multiple dilutions
    # selection_type = 'chemical' # either 'chemical' eg. antibiotics or 'environmental' eg. temperature
    # selection_var = 'abx' # the eVOLVER command name for the selection variable; eg. 'abx' for antibiotics or 'temp' for temperature

    ### End of Stepped Evolution Settings ###

    ##### END OF USER DEFINED VARIABLES #####

    ##### ADVANCED SETTINGS #####
    ## Turbidostat Settings ##
    #Tunable settings for overflow protection, pump scheduling etc. Unlikely to change between expts
    time_out = 5 #(sec) additional amount of time to run efflux pump
    pump_wait = 20 # (min) minimum amount of time to wait between pump events
    ## End of Turbidostat Settings ##

    ## General Fluidics Settings ##
    flow_rate = eVOLVER.get_flow_rate() #read from calibration file
    bolus_fast = 0.5 #mL, can be changed with great caution, 0.2 is absolute minimum
    bolus_slow = 0.1 #mL, can be changed with great caution
    max_gap = 0.2 # hours; time gap to count as a pause in the experiment and thus ignore for step timing
    dilution_window = 3 # window on either side of a dilution to calculate dilution effect on OD
    ## End of General Fluidics Settings ##
    
    ##### END OF ADVANCED SETTINGS #####
    
    ##### VARIABLE INITIALIZATION #####
    ## Check that min_selection is high enough given stock concentration and bolus_slow ##
    for i, vial in enumerate(turbidostat_vials):
        if vial in selection_steps: # if steps defined manually
            min_selection = selection_steps[vial][0]
            max_selection = selection_steps[vial][-1]
        else:
            min_selection = min_selections[i]
            max_selection = max_selections[i]
        if min_selection > max_selection:
            logger.warning(f"Vial {vial}: min_selection {min_selection} must be less than max_selection {max_selection}.")
            eVOLVER.stop_exp()
            print('Experiment stopped, goodbye!')
            logger.warning('experiment stopped, goodbye!')
            raise ValueError(f"Vial {vial}: min_selection {min_selection} must be less than max_selection {max_selection}.")
        
        # Calculate concentration with the smallest bolus we can add
        min_conc = ((selection_stock_concs[vial] * bolus_slow) + (0 * VOLUME)) / (bolus_slow + VOLUME) # Adding bolus_slow stock into plain media
        if min_conc > min_selection:
            # Solve for stock concentration that will be able to add bolus_slow and reach min_conc
            new_stock_conc = ((min_selections[i] * (bolus_slow + VOLUME)) - (min_conc * VOLUME)) / bolus_slow
            logger.warning(f"Vial {vial}: min_selection must be greater than {round(min_conc, 3)}. Decrease stock concentration to at least {int(new_stock_conc)}.")
            eVOLVER.stop_exp()
            print('Experiment stopped, goodbye!')
            logger.warning('experiment stopped, goodbye!')
            raise ValueError(f"Vial {vial}: min_selection must be greater than {round(min_conc, 3)}. Decrease stock concentration to at least {int(new_stock_conc)}.")

    ## Selection Step Automatic Generation ##
    if generate_steps: # generate steps automatically
        for i, vial in enumerate(turbidostat_vials):
            if min_selections[i] - max_selections[i] == 0:
                selection_steps[vial] = [min_selections[i]]
            elif log_steps:
                if min_selections[i] <= 0: # check if min_selection is greater than 0
                    logger.warning(f"Vial {vial}: min_selection must be greater than 0 for logarithmic steps.")
                    eVOLVER.stop_exp()
                    print('Experiment stopped, goodbye!')
                    logger.warning('experiment stopped, goodbye!')
                    raise ValueError(f"Vial {vial}: min_selection must be greater than 0 for logarithmic steps.") # raise an error if min_selection is less than 0
                selection_steps[vial] = np.round(np.logspace(np.log10(min_selections[i]), np.log10(max_selections[i]), num=selection_step_nums[i]), 3)
            else:
                selection_steps[vial] = np.round(np.linspace(min_selections[i], max_selections[i], num=selection_step_nums[i]), 3)
    
    # Compare current selection settings to previous and print if they have changed
    for i, vial in enumerate(turbidostat_vials):
        current_config = [elapsed_time] + selection_steps[vial]
        config_change = su.compare_configs('step', vial, current_config) # Check if config has changed and write to file if it has
        if config_change: # Print and log if the config is updated
            if generate_steps:
                print(f"Generated {selection_step_nums[i]} steps for vial {vial}: {min_selections[i]} to {max_selections[i]}")
            print(f"Step config changed| New Steps:\n {selection_steps[vial]}")
            logger.info(f"Vial {vial} step config changed| New Steps: {selection_steps[vial]}")
            
            # Update log file with new steps
            current_conc = su.get_last_n_lines('step_log', vial, 1)[0][3] # Format: [elapsed_time, step_time, current_step, current_conc]
            file_name =  f"vial{vial}_step_log.txt"
            file_path = os.path.join(eVOLVER.exp_dir, EXP_NAME, 'step_log', file_name)
            text_file = open(file_path, "a+")
            text_file.write(f"{elapsed_time},0,{round(selection_steps[vial][0], 3)},{current_conc}\n") # Format: [elapsed_time, step_time, current_step, current_conc]
            text_file.close()
            logger.info(f"Vial {vial} step log updated to first step: {round(selection_steps[vial][0], 3)}")
    ## End of Selection Step Initialization ##
    

    ##### END OF VARIABLE INITIALIZATION #####

    light_MESSAGE = ['--'] * 32 # initializes light message
    light_cal = eVOLVER.get_light_vals() # read from calibration file

    ##### Turbidostat Control Code Below #####

    # fluidic message: initialized so that no change is sent
    MESSAGE = ['--'] * 48
    for x in turbidostat_vials: #main loop through each vial
        # Update turbidostat configuration files for each vial
        # initialize OD and find OD path

        file_name =  "vial{0}_ODset.txt".format(x)
        ODset_path = os.path.join(eVOLVER.exp_dir, EXP_NAME, 'ODset', file_name)
        data = np.genfromtxt(ODset_path, delimiter=',')
        ODset = data[len(data)-1][1]
        ODsettime = data[len(data)-1][0]
        num_curves=len(data)/2;

        file_name =  "vial{0}_OD.txt".format(x)
        OD_path = os.path.join(eVOLVER.exp_dir, EXP_NAME, 'OD', file_name)
        data = eVOLVER.tail_to_np(OD_path, OD_values_to_average)
        average_OD = 0

        # Determine whether turbidostat dilutions are needed
        #enough_ODdata = (len(data) > 7) #logical, checks to see if enough data points (couple minutes) for sliding window
        collecting_more_curves = (num_curves <= (stop_after_n_curves + 2)) #logical, checks to see if enough growth curves have happened

        if data.size != 0:
            # Take median to avoid outlier
            od_values_from_file = data[:,1]
            average_OD = float(np.median(od_values_from_file))

            #if recently exceeded upper threshold, note end of growth curve in ODset, allow dilutions to occur and growthrate to be measured
            if (average_OD > upper_thresh[x]) and (ODset != lower_thresh[x]):
                text_file = open(ODset_path, "a+")
                text_file.write("{0},{1}\n".format(elapsed_time,
                                                   lower_thresh[x]))
                text_file.close()
                ODset = lower_thresh[x]
                # calculate growth rate
                eVOLVER.calc_growth_rate(x, ODsettime, elapsed_time)

            #if have approx. reached lower threshold, note start of growth curve in ODset
            if (average_OD < (lower_thresh[x] + (upper_thresh[x] - lower_thresh[x]) / 3)) and (ODset != upper_thresh[x]):
                text_file = open(ODset_path, "a+")
                text_file.write("{0},{1}\n".format(elapsed_time, upper_thresh[x]))
                text_file.close()
                ODset = upper_thresh[x]

            #if need to dilute to lower threshold, then calculate amount of time to pump
            if average_OD > ODset and collecting_more_curves:

                time_in = - (np.log(lower_thresh[x]/average_OD)*VOLUME)/flow_rate[x]

                if time_in > 20:
                    time_in = 20

                time_in = round(time_in, 2)

                file_name =  "vial{0}_pump_log.txt".format(x)
                file_path = os.path.join(eVOLVER.exp_dir, EXP_NAME,
                                         'pump_log', file_name)
                data = np.genfromtxt(file_path, delimiter=',')
                last_pump = data[len(data)-1][0]
                if ((elapsed_time - last_pump)*60) >= pump_wait: # if sufficient time since last pump, send command to Arduino
                    logger.info('turbidostat dilution for vial %d' % x)
                    # influx pump
                    MESSAGE[x] = str(time_in)
                    # efflux pump
                    MESSAGE[x + 16] = str(time_in + time_out)

                    file_name =  "vial{0}_pump_log.txt".format(x)
                    file_path = os.path.join(eVOLVER.exp_dir, EXP_NAME, 'pump_log', file_name)

                    text_file = open(file_path, "a+")
                    text_file.write("{0},{1}\n".format(elapsed_time, time_in))
                    text_file.close()
        else:
            logger.debug('not enough OD measurements for vial %d' % x)

    ##### END OF Turbidostat Control Code #####
    
    ##### SELECTION LOGIC #####
    for vial in turbidostat_vials:
        # Get all growth rate data for this vial (read in as a Pandas dataframe)
        file_name =  f"vial{vial}_gr.txt"
        gr_path = os.path.join(eVOLVER.exp_dir, EXP_NAME, 'growthrate', file_name)
        gr_data = gr_data = pd.read_csv(gr_path, delimiter=',', header=1, names=['time', 'gr'], dtype={'time': float, 'gr': float})

        # Check for selection start
        if len(gr_data) >= curves_to_wait: # If the number of growth curves is more than the number we need to wait
            steps = selection_steps[vial]

            # Find the current selection step
            step_log = su.get_last_n_lines('step_log', vial, dilution_window*2)
            last_step_log = step_log[-1] # Format: [elapsed_time, step_time, current_step, current_conc]
            last_time = last_step_log[0] # time of the last step log
            last_step_time = last_step_log[1] # time spent on the current selection level
            current_step = last_step_log[2] # current selection target level (chemical concentration)
            last_conc = last_step_log[3] # current selection chemical concentration in the vial
            
            ## Initialize Variables ##
            step_time = last_step_time # step time is the same as the last step time
            time_diff = elapsed_time - last_time # time since last step_log entry
            if time_diff < max_gap: # if there was a large time gap, don't add to step_time
                step_time += time_diff # add the time since last step_log entry to the step time
            closest_step_index = np.argmin(np.abs(steps - current_step)) # Find the index of the closest step to the current step
            current_conc = last_conc # Initialize the current concentration to the last concentration
            next_step = current_step # Initialize the next step to the current step
            
            if closest_step_index == 0 and step_time == 0:
                logger.info(f"Starting selection in vial {vial}")
                print(f"Starting selection in vial {vial}")
            if closest_step_index == len(steps) - 2: # Warn the user that they are on second to last step
                logger.info(f"WARNING: Reached second to last selection step in vial {vial}: {current_step} | Change step range")
                print(f"WARNING: Reached second to last selection step in vial {vial}: {current_step} | Change step range")

            ## Selection Level Logic ## 
            # Decision: whether to go to next step, decrease to previous step, or stay at current step
            if (step_time >= min_step_time) and (len(steps) != 1):
                last_gr_time = gr_data['time'].values[-1] # time of the last growth rate measurement (ie dilution time)
                last_gr = gr_data.tail(curves_to_wait)['gr'].median() # median growth rate over the last dilutions

                # Decrease to the previous selection level because selection level is too high
                if ((elapsed_time - last_gr_time) > growth_stalled_time) or (last_gr < min_growthrate):
                    if closest_step_index - 1 == 0:
                        next_step = steps[closest_step_index - 1]
                        logger.info(f"WARNING: Decreasing to first selection step in vial {vial}: {next_step} | Change step range or change growth rate requirements")
                        print(f"WARNING: Decreasing to first selection step in vial {vial}: {next_step} | Change step range or change growth rate requirements")
                    elif closest_step_index - 1 < 0:
                        next_step = 0
                        logger.info(f"WARNING: Unable to grow on first selection step in vial {vial}: {current_step} | Decreasing selection to 0 in vial | Change step range or change growth rate requirements")
                        print(f"WARNING: Unable to grow on first selection step in vial {vial}: {current_step} | Decreasing selection to 0 in vial | Change step range or change growth rate requirements")
                    else:
                        next_step = steps[closest_step_index - 1]
                        logger.info(f"Vial {vial}: DECREASE | Decreasing selection from {current_step} to {next_step}")
                        print(f"Vial {vial}: DECREASE | Decreasing selection from {current_step} to {next_step}")

                    step_time = 0 # Reset the step time

                    if rescue_dilutions: # Make a dilution to rescue cells to lower selection level
                        # Calculate the amount to dilute to reach the new selection level
                        dilution_factor = next_step / current_step
                        time_in = - (np.log(dilution_factor)*VOLUME)/flow_rate[vial] # time to dilute to the new selection level
                        if time_in > 20: # Limit the time to dilute to 20
                            time_in = 20
                            dilution_factor = np.exp((time_in*flow_rate[vial])/(-VOLUME))
                            print(f'Vial {vial}: RESCUE DILUTION | Unable to dilute to {next_step} (> 20 seconds pumping) | Diluting by {round(dilution_factor, 3)} fold')
                        else:
                            print(f'Vial {vial}: RESCUE DILUTION | Diluting by {round(dilution_factor, 3)} fold')
                        current_conc = last_conc * dilution_factor
                        time_in = round(time_in, 2)
                        MESSAGE[x] = str(time_in) # influx pump
                        MESSAGE[x + 16] = str(time_in + time_out) # efflux pump

                        file_name =  f"vial{vial}_pump_log.txt"
                        file_path = os.path.join(eVOLVER.exp_dir, EXP_NAME, 'pump_log', file_name)
                        text_file = open(file_path, "a+")
                        text_file.write("{0},{1}\n".format(elapsed_time, time_in))
                        text_file.close()
                        logger.info(f'Vial {vial}: RESCUE DILUTION | Diluting by {dilution_factor} fold')
                        print(f'Vial {vial}: RESCUE DILUTION | Diluting by {dilution_factor} fold')
                                        
                # Increase to the next selection level because selection level is too low
                elif last_gr > max_growthrate:
                    if closest_step_index < len(steps) - 1: # If there is a next step
                        next_step = steps[closest_step_index + 1]
                    elif closest_step_index == len(steps) - 1: # If there is no next step
                        logger.info(f"Vial {vial}: Reached MAXIMUM selection | {current_step}")
                        print(f"Vial {vial}: Reached MAXIMUM selection | {current_step}")
                    step_time = 0 # Reset the step time
                    logger.info(f"Vial {vial}: INCREASE | Increasing selection from {current_step} to {next_step}")
                    print(f"Vial {vial}: INCREASE | Increasing selection from {current_step} to {next_step}")

                current_step = next_step # Update the current step

            ## Selection Fluidics ##
            # Load the last pump event
            last_dilution = su.get_last_n_lines('pump_log', vial, 1)[0] # Format: [elapsed_time, time_in]
            last_dilution_time = last_dilution[0] # time of the last pump event

            # Calculate the dilution factor based off of proportion of OD change
            OD_data = su.get_last_n_lines('OD', vial, dilution_window*2) # Get OD data from before and after dilution
            OD_times = OD_data[:, 0]
            if last_dilution_time == OD_times[-(dilution_window+1)]: # Waiting until we have dilution_window length OD data before and after dilution 
                # Calculate current concentration of selection chemical
                OD_before = np.median(OD_data[:dilution_window, 1]) # Find OD before and after dilution
                OD_after = np.median(OD_data[-dilution_window:, 1])
                dilution_factor = OD_after / OD_before # Calculate dilution factor
                current_conc = last_conc * dilution_factor
                # TODO rewrite last dilution_window steps to this concentration

            # Determine whether to add chemical to vial
            conc_ratio = current_conc / current_step
            if conc_ratio < 0:
                # Calculate amount of chemical to add to vial; derived from concentration equation:: C_final = [C_a * V_a + C_b * V_b] / [V_a + V_b]
                calculated_bolus = (VOLUME * (current_conc - current_step)) / (current_step - selection_stock_concs[vial]) # in mL, bolus size of stock to add
                if calculated_bolus > 5: # prevent more than 5 mL added at one time to avoid overflows
                    print(f'Vial {vial}: Selection chemical bolus too large: adding 5mL')
                    logger.info(f'Vial {vial}: Selection chemical bolus too large: adding 5mL')
                    calculated_bolus = 5
                    # Update current concentration because we are not bringing to full target conc
                    current_conc = ((selection_stock_concs[vial] * calculated_bolus) + (current_conc * VOLUME)) / (calculated_bolus + VOLUME) 
                elif calculated_bolus < bolus_slow:
                    logger.info(f'Vial {vial}: Selection chemical bolus too small: current concentration {current_conc} to current step {current_step}')
                
                time_in = calculated_bolus / float(flow_rate[vial + 32]) # time to add bolus
                time_in = round(time_in, 2)
                MESSAGE[vial + 32] = str(time_in) # set the pump message
                
                print(f'Vial {vial}: Selection chemical bolus added: {round(calculated_bolus, 3)}mL')
                logger.info(f'Vial {vial}: Selection chemical bolus added: {round(calculated_bolus, 3)}mL')

                # Update slow pump log
                file_name =  f"vial{vial}_slow_pump_log.txt"
                file_path = os.path.join(eVOLVER.exp_dir, EXP_NAME, 'slow_pump_log', file_name)
                text_file = open(file_path, "a+")
                text_file.write("{0},{1}\n".format(elapsed_time, time_in))
                text_file.close()

            # Log current selection state
            file_name =  f"vial{vial}_step_log.txt"
            file_path = os.path.join(eVOLVER.exp_dir, EXP_NAME, 'step_log', file_name)
            text_file = open(file_path, "a+")
            text_file.write(f"{elapsed_time},{step_time},{current_step},{current_conc}\n") # Format: [elapsed_time, updated step_time, current_step, current_conc]
            text_file.close()
            
            
        #### LIGHT CONTROL CODE BELOW ####
        if elapsed_time < TIME_TO_FINAL: # check if initial acclimation period is over
            light_uE = LIGHT_INITIAL[x]
        else:
            light_uE = LIGHT_FINAL[x]
        light_pwm = int((float(light_uE) - light_cal[x][1]) / light_cal[x][0]) # convert light value to PWM value (based on linear calibration)

        ## Log light values in light_config file ##
        file_name =  "vial{0}_light_config.txt".format(x)
        light_config_path = os.path.join(eVOLVER.exp_dir, EXP_NAME,
                                        'light_config', file_name) 
        light_config = np.genfromtxt(light_config_path, delimiter=',', skip_header=1) #format: (time, light1 uE, PWM value 1, light2 uE, PWM value 2)
        if light_config.ndim != 1: #np.genfromtext gives a 1D array if there's only one line, but 2D otherwise
            light_config = light_config[-1] #get last line
        last_light_time = light_config[0] #time of last light command
        last_light_uE = light_config[1] #last light value in uE
        last_light_pwm = light_config[2] #last light value in eVOLVER PWM units

        light_MESSAGE[x] = light_pwm

        if light_uE != last_light_uE: #log the new light values
            print(f'Light updated in vial {x}, uE {light_uE}, PWM {light_pwm}')
            logger.info(f'Light updated in vial {x}: uE {light_uE}, PWM {light_pwm}')
            # writes command to light_config file, for storage
            text_file = open(light_config_path, "a+")
            text_file.write(f'{elapsed_time},{light_uE},{light_pwm},0,0\n')
            text_file.close()

    # send fluidic command only if we are actually turning on any of the pumps
    if MESSAGE != ['--'] * 48:
        eVOLVER.fluid_command(MESSAGE)

if __name__ == '__main__':
    print('Please run eVOLVER.py instead')
    logger.info('Please run eVOLVER.py instead')

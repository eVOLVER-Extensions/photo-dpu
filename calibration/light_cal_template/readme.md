# Purpose:
	Calibrate a single vial at a time using the LI-1500 probe

# Command:
	python3 light_cal.py <vial_num>
# Example:
	python3 light_cal.py 5

# Protocol:
1. Set up probe in vial using calibration cap
2. Alter calibration_vals in calibrate_light.py
3. Start loggger
	- Turn on via mini-USB power cable plug on top
	- Press "START"
	- New file > Label with vial number > OK > Water probe
	- Should be changing values now
4. Run this program
	- python3 light_cal.py <vial_num>
	- Sets eVOLVER  light for that vial to each value
	- Separates values in the LI-1500 log by turning off the light
5. Stop logging (or turn off probe)
6. Do for each vial
7. Make a folder in Calibrations with the name of this light cal
8. Plug logger in to the computer via USB
9. Transfer files over to folder you made
10. Run analyze_light_cal.ipynb
11. Transfer your calibration file to your experiment template folder

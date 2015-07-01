# example script using the Keithley2400 python class to do a simple IV curve measurement

from keithley import Keithley2400

GPIBaddr = 23  # use whatever your keithley's GBIP address is

# set sweep parameters (in volts)
minV = -5E-3
maxV = 5E-3
sourceStepV = 1E-4  # voltage step
sourceStepT = 0.1  # time step

k = Keithley2400(GPIBaddr)

# to do a single sweep from minV to maxV
k.setSourceSweep('voltage', minV, maxV, sourceStepV, sourceStepT)
k.doMeasurement()
k.saveData('/users/henry/pythonData/', 'IVmeasurement.txt')

# to sweep from minV to maxV back to minV
k.setSourceSweep('voltage', minV, maxV, sourceStepV, sourceStepT)  # sweep from minV to maxV
k._startMeasurement()
k._pullData()
k.setSourceSweep('voltage', maxV, minV, -sourceStepV, sourceStepT)  # sweep from maxV to minV
k._startMeasurement()
k._pullData()
k._stopMeasurement()
k.saveData('/users/henry/pythonData/', 'IVmeasurement.txt')

# to ramp the applied voltage up slowly, instead of as a step function
k.rampOutputOn(minV, sourceStepV)
k.setSourceSweep('voltage', minV, maxV, sourceStepV, sourceStepT)  # sweep from minV to maxV
k._startMeasurement()
k._pullData()
k.setSourceSweep('voltage', maxV, minV, -sourceStepV, sourceStepT)  # sweep from maxV to minV
k._startMeasurement()
k._pullData()
k.rampOutputOff(minV, sourceStepV)
k._stopMeasurement()

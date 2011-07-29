try:
	import niScope
except e:
	print "niScope missing, continuing anyway"
try:
	from nidaqmx import AnalogOutputTask
except e:
	print "nidaqmx missing, continuing anyway"
import ordered_symbols
import logging
import numpy as np
import matplotlib.pyplot as plt
from configobj import ConfigObj
from validate import Validator
from time import sleep
from multiprocessing import Process, Queue
from path import *

def log_type(value):
	try:
		return getattr(logging,value)
	except AttributeError:
		pass
	return int(value)	

def scan(scope,daq):
	scope.InitiateAcquisition()
	daq.start()
	while scope.AcquisitionStatus() != niScope.NISCOPE_VAL_ACQ_COMPLETE:
		sleep(0.1)
	scope.Fetch("",data)
	return data

def processor(queue):
	raw_data = queue.get()
	rsp_data = reample(raw_data)

def param(config):
	daq = config['daq']
	path = daq['path']
	laser_sweep_frequency = config['laser']['frequency']
	density = config['image']['density']
	xlength = path['xf']-path['x0']
	ylength = path['yf']-path['y0']
	length = np.sqrt(xlength**2+ylength**2)
	numRecords = density*length
	config['scope']['Horizontal']['numRecords'] = numRecords
	scan_time = numRecords/laser_sweep_frequency
	x_vel = xlength/scan_time
	y_vel = ylength/scan_time
	daq_sample_rate = daq['positioning_time']
	num_points = daq_sample_rate*daq['positioning']['rate']
	if mode == 'position':
		return path['x0'],path['y0'],x_vel,y_vel,scan_time,numPoints

def position(config):
	path = make_2d_position_path(param(config,'position'))
	daq = prepare_daq(path,daq_config,'positioning')
	time.wait_until(daq.task_done)
	del daq

def park(daq):
	position([0,0],daq)

def prepare_daq(path,daq_config,mode,auto_start=True):
	X_mpV = daq_config['X_mpV']
	Y_mpV = daq_config['Y_mpV']
	T = np.array([[X_mpV,Y_mpV]]).T
	signal = path*T
	daq = AnalogOutputTask()
	daq.create_voltage_channel(**daq_config['X'])
	daq.create_voltage_channel(**daq_config['Y'])
	daq.configure_timing_sample_clock(**daq_config[mode])
	daq.write(signal,auto_start=auto_start)
	return daq

def prepare_scope(scope_config):
	scope = niScope.Scope(scope_config['dev'])
	scope.ConfigureHorizontalTiming(**scope_config['Horizontal'])
	scope.ExportSignal(**scope_config['ExportSignal'])
	scope.ConfigureTrigger(**scope_config['Trigger'])
	scope.ConfigureVertical(**scope_config['VerticalRef'])
	scope.ConfigureVertical(**scope_config['VerticalSample'])
	return scope

def resample(raw_data,config):
	from scipy import interpolate
	import matplotlib.pyplot as plt
	p = [config['p%d'%i] for i in range(8)]
	f = np.poly1d(p)
	old_x = f(np.arange(raw_data.shape[-1]))
	new_x = np.linspace(0,raw_data.shape[-1],1024)
	resampled = np.zeros((raw_data.shape[0],1024))
	if len(raw_data.shape) == 1:
		tck = interpolate.splrep(old_x,raw_data,s=0)
		resampled = interpolate.splev(new_x,tck)
	else:
		for line in range(raw_data.shape[0]):
			tck = interpolate.splrep(old_x,raw_data[line])
			resampled[line] = interpolate.splev(new_x,tck)
	return resampled

def transform(rsp_data):
	return abs(np.fft.fft(data))

def allocate_memory(config):
	hor = config['Horizontal']
	X = hor['numPts']
	Y = hor['numRecords']
	Z = config['numTomograms']
	data = np.zeros([Z,X,Y],order='C',dtype=np.float64)
	return data

def positioning(daq_task,config):
	config['daq']['positioning']
	task.configure_timing_sample_clock(source='OnboardClock', rate=1, active_edge='rising', sample_mode='finite', samples_per_channel=1000)
	
def make_line_path(x0,y0,xf,yf,N):
	X = np.linspace(x0,xf,N)
	Y = np.linspace(y0,yf,N)
	return np.vstack((X,Y))

def make_setpositionpath():
	pass

def make_resetpositionpath():
	pass

def make_acquisitionwindowpath():
	pass

def make_parkpath():
	pass

def horz_cal(config,data):
	scope_config = config['scope']
	scope = prepare_scope(config['scope'])
	scope.InitiateAcquisition()
	num = scope_config['Horizontal']['numPts']
	rec = scope_config['Horizontal']['numRecords']*2
	data = np.zeros((num,rec),order='F',dtype=np.float64)
	scope.Fetch('0,1',data)
	np.savetxt('ref.dat',data,fmt='%.18e')
	return data

def load(config,data):
	data = np.loadtxt('ref.dat').T
	return data[0]

def non_cor_fft(config,data):
	return abs(np.fft.fft(data))

def get_p(config,data):
	data =  y > 0
	t = np.logical_xor(data,np.roll(data,1))
	size = len(y)
	zero_x = np.arange(size)[t]
	zero_y = np.linspace(0,zero_x[-1],len(zero_x))
	data = zero_x
	p = np.polyfit(zero_x,zero_y,7)
	f = np.poly1d(p)
	data = np.vstack([zero_y,f(zero_x)]).T
	for i in p:
		config['resample_poly_coef']['p%d'%np.where(p==i)] = i
	config.write()	
	return data

def scan(config,data):
	image_config = config['image']
	lineDensity = image_config['density']
	length = image_config['length']
	X = single_scan_path(-length/2,length/2,50,lineDensity)
	path = np.vstack([X,np.zeros(X.shape)]).T
	daq = prepare_daq(path,config['daq'],"positioning")
	scope = prepare_scope(scope_config)
	scope.NumRecords = path.shape[1]
	raw_data = scan(scope,daq)
	rsp_data = resample(raw_data)
	fft_data = transform(rsp_data)
	abs_data = abs(fft_data)

def scan_3d(config,data):
	config3D = config["scope3D"]
	data = allocate_memory(config3D)
	scope = prepare_scope(config3D)
	numTomograms = config3D['numTomograms']
	conf = config['daq']['positioning']
	f = config['laser']['frequency']
	path = config['daq']['path'] 
	numRec = config3D['Horizontal']['numRecords']
	tf = float(numRec)/f
	r = (path['xf']-path['x0'])/tf
	N = conf['samples_per_channel']
	x0,xf,y0,yf=path['x0'],path['xf'],path['y0'],path['yf']
	return_path = make_return_path(x0,xf,y0,yf,tf,r,N,numTomograms)
	scan_path = make_scan_path(x0,xf,y0,yf,numRec,numTomograms)
	for i in range(numTomograms):
		tomogram = data[i]
		daq = prepare_daq(scan_path[i],config['daq'],"scan3D")
		scope.InitiateAcquisition()
		scope.Fetch(config3D['VerticalSample']['channelList'],tomogram)
		del daq
		daq = prepare_daq(return_path[i],config['daq'],"positioning",auto_start=True)
		daq.wait_until_done()
		del daq
	# numpy arrays and niscope arrays have weird order, code below fix it
	new_shape = [data.shape[i] for i in [0,2,1]]
	data = data.reshape(new_shape)
	return data

def scan_continuous(config,data):
	arg = config['daq']['path'].dict()
	arg['N'] = config['scope']['Horizontal']['numRecords']
	scan_path = make_line_path(**arg)
	position(scan_path[0],daq)
	scope = prepare_scope(config['scope'])
	while go:
		daq = prepare_daq(scan_path,config['daq'],'scanContinuous'):
		scope.InitiateAcquisition()
		scope.Fetch('0',data)
		del daq
		return_mirror(config)
		data = process(data)
		plt.imshow(data)
	park(daq)

def resample(config,data):
	if len(data.shape) == 3:
		data = data[0,:,:]
	return resample(data,config['resample_poly_coef'])

def fft(config,data):
	data = abs(np.fft.fft(data))

def plot(config,data):
	import matplotlib.pyplot as plt
	if len(data.shape) == 3:
		data = data[0,0,:]
	if len(data.shape) == 2:
		if data.shape[1] == 2:
			plt.plot(data[0],data[1])
			plt.show()
			return
	plt.plot(data)
	plt.show()

def img_plot(config,data):
	if len(data.shape) == 3:
		data = data[0]
	if len(data.shape) == 2:
		data = data
	import matplotlib.pyplot as plt
	plt.imshow(data)
	plt.show()

def store(config,data):
	filename = "data.dat"
	np.savetxt(filename,data)

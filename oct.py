import niScope
import ordered_symbols
import logging as log
import numpy as np
import matplotlib.pyplot as plt
from configobj import ConfigObj
from validate import Validator
from nidaqmx import AnalogOutputTask
from time import sleep
from multiprocessing import Process, Queue

def log_type(value):
	try:
		return getattr(log,value)
	except AttributeError:
		pass
	return int(value)	

validator = Validator({'log':log_type,'float':float})

def parse():
	import argparse
	parser = argparse.ArgumentParser()
	parser.description = "OCT client."
	parser.add_argument('--horz-cal',action='store_true')
	parser.add_argument('--plot',action='store_true')
	parser.add_argument('--img-plot',action='store_true')
	parser.add_argument('--store',action='store_true')
	parser.add_argument('--x',action='store_true')
	parser.add_argument('--get-p',action='store_true')
	parser.add_argument('--resample',action='store_true')
	parser.add_argument('--fft',action='store_true')
	parser.add_argument('--non-cor-fft',action='store_true')
	parser.add_argument('--line',action='store_true')
	parser.add_argument('--scan-3D',action='store_true')
	parser.add_argument('--scan-continuous',action='store_true')
	parser.add_argument('--scan',action='store_true')
	return parser.parse_args()

def scan(scope,daq):
	scope.InitiateAcquisition()
	daq.start()
	while scope.AcquisitionStatus() != niScope.NISCOPE_VAL_ACQ_COMPLETE:
		sleep(0.1)
	scope.Fetch("",data)
	return data

def position(point,daq):
	pass

def park(daq):
	position([0,0],daq)

def prepare_daq(path,daq_config,mode,auto_start):
	daq = AnalogOutputTask()
	daq.create_voltage_channel(**daq_config['X'])
	daq.create_voltage_channel(**daq_config['Y'])
	daq.configure_timing_sample_clock(**daq_config['positioning'])
	daq.write(path,auto_start=auto_start)
	return daq

def prepare_scope(scope_config):
	scope = niScope.Scope(scope_config['dev'])
	log.debug('Scope initialized ok')
	scope.ConfigureHorizontalTiming(**scope_config['Horizontal'])
	log.debug('Scope horizontal configured')
	scope.ExportSignal(**scope_config['ExportSignal'])
	scope.ConfigureTrigger(**scope_config['Trigger'])
	log.debug('Scope trigger configured')
	scope.ConfigureVertical(**scope_config['VerticalRef'])
	log.debug('Scope ref configured')
	scope.ConfigureVertical(**scope_config['VerticalSample'])
	log.debug('Scope sample configured')
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

def line(begin,end,lineDensity):
	lineDensity = float(lineDensity)
	v = np.array(end) - np.array(begin)
	length = np.sqrt(sum(v**2))
	t = np.linspace(0,1,length*lineDensity)	
	t.shape += (1,)
	line = begin + v*t
	return line.T

def poly3(x1,x2,t1,t2,r1,r2):
	"""
	Returns the polynomial coeficients for a curve with the position and the
	derivative defined at two points of the curve.
	"""
	from numpy.linalg import solve
	A = np.array([
	[	3*t1**2,	2*t1, 	1,	0	],
	[	3*t2**2,	2*t2,	1,	0	],
	[	t1**3  , 	t1**2,	t1,	1	],
	[	t2**3  , 	t2**2,	t2,	1	],
	])
	B = np.array([r1, r2, x1, x2])
	return solve(A,B)

def make_scan_path(x0,xf,y0,yf,numRecords,numTomograms):
	x = np.linspace(x0,xf,numRecords)
	x.shape = (1,) + x.shape
	X = x*np.ones((numTomograms,1))
	y = np.linspace(y0,yf,numTomograms)
	y.shape = y.shape + (1,)
	Y = y*np.ones(numRecords)
	scan_path = np.dstack([X,Y])
	return scan_path

def third_order_line(x1,x2,t1,t2,r1,r2):
    	f = np.poly1d(poly3(x1,x2,t1,t2,r1,r2))
	return f(np.arange(t1,t2))

def single_scan_path(X0,Xf,t,lineDensity):
	pitch = 1/float(lineDensity)
	num = (Xf-X0)*lineDensity
	start = third_order_line(0,X0,0,t,0,pitch)
	scan = np.linspace(X0,Xf,num)
	park = third_order_line(Xf,0,0,t,pitch,0)
	return np.hstack([start,scan[0:-1],park])
    	
def positioning(daq_task,config):
	config['daq']['positioning']
	task.configure_timing_sample_clock(source='OnboardClock', rate=1, active_edge='rising', sample_mode='finite', samples_per_channel=1000)
	
def make_setpositionpath():
	pass

def make_resetpositionpath():
	pass

def make_acquisitionwindowpath():
	pass

def make_parkpath():
	pass

arg = parse()
config = ConfigObj('config.ini',configspec='configspec.ini')
if not config.validate(validator):
	raise Exception('config.ini does not validate with configspec.ini.')
log.basicConfig(filename='oct.log',level=config['log'])
scope_config = config['scope']
if arg.line:
	print line([1,0],[2,3],10)

if arg.horz_cal:
	scope = prepare_scope(config['scope'])
	scope.InitiateAcquisition()
	num = scope_config['Horizontal']['numPts']
	rec = scope_config['Horizontal']['numRecords']*2
	print "Actual record length = ",scope.ActualRecordLength
	print "Actual sample rate = ",scope.ActualRecordLength
	data = np.zeros((num,rec),order='F',dtype=np.float64)
	scope.Fetch('0,1',data)
	np.savetxt('ref.dat',data,fmt='%.18e')
	x = None
			
data = np.loadtxt('ref.dat').T
data = data[0]
y = data
if arg.non_cor_fft:
	data = abs(np.fft.fft(data))

if arg.get_p:
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
	x = zero_x



if arg.scan:
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

if arg.scan_3D:
#	path = loadpath()
#	position(path[0],daq)
	config3D = config["scope3D"]
	data = allocate_memory(config3D)
#	daq.write(path)
	scope = prepare_scope(config3D)
#	queue = Queue()
#	reposition_path = third_order_line(Xf,X0,0,10,pitch,pitch)
#	scan = np.linspace(X0,Xf,num)
#	path = np.hstack((scan,reposition_path))
#	daq = prepare_daq(path,config['daq'],"positioning")
#	daq.close()
	numTomograms = config3D['numTomograms']
#	scan_path = 
#	return_path
	for i in range(numTomograms):
		tomogram = data[i]
		daq = prepare_daq(scan_path[i],config['daq'],"scan3D")
		scope.InitiateAcquisition()
		scope.Fetch(config3D['VerticalSample']['channelList'],tomogram)
		del daq
		daq = prepare_daq(return_path[i],config['daq'],"positioning",auto_start=True)
		daq.wait_until_done()
		del daq
#		queue.put(tomogram)
	# numpy arrays and niscope arrays have weird order, code below fix it
	new_shape = [data.shape[i] for i in [0,2,1]]
	data = data.reshape(new_shape)

#	p.start()
#	park(daq)

def processor(queue):
	raw_data = queue.get()
	rsp_data = reample(raw_data)

if arg.scan_continuous:
	path = loadpath()
	position(path[0],daq)
	daq.configure_timing_sample_clock(**daq_config['scanContinuous'])
	daq.write(path)
	park(daq)

if arg.resample:
	if len(data.shape) == 3:
		data = data[0,:,:]
	data = resample(data,config['resample_poly_coef'])
	x = None 

if arg.fft:
	data = abs(np.fft.fft(data))

if arg.plot:
	if len(data.shape) == 3:
		data = data[0,0,:]
		x = None
	if len(data.shape) == 2:
		data = data[0]
		x = None
	if x is None:
		x = np.arange(len(data))
	import matplotlib.pyplot as plt
	plt.plot(x,data)
	plt.show()

if arg.img_plot:
	if len(data.shape) == 3:
		data = data[0]
	if len(data.shape) == 2:
		data = data
	import matplotlib.pyplot as plt
	plt.imshow(data)
	plt.show()

if arg.store:
	filename = "data.dat"
	np.savetxt(filename,data)

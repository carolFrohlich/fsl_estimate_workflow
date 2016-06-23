import os                                    # system functions
import yaml
import nipype.interfaces.utility as util
import nipype.interfaces.io as nio           # Data i/o
import nipype.interfaces.fsl as fsl          # fsl
import nipype.pipeline.engine as pe          # pypeline engine
import nipype.algorithms.modelgen as model   # model generation
from nipype.interfaces.base import Bunch
from CPAC.registration import create_wf_apply_ants_warp
from nipype.workflows.fmri.fsl import (create_featreg_preproc,
                                       create_modelfit_workflow,
                                       create_reg_workflow)


#template = '/usr/share/fsl/5.0/data/standard/MNI152_T1_2mm_brain.nii.gz'
template = '/usr/share/fsl/5.0/data/standard/MNI152_T1_2mm_brain_symmetric.nii.gz'


# import csv
# with open('data/fristons_twenty_four.1D', 'rb') as f:
#     a = [list(map(float,rec)) for rec in csv.reader(f, delimiter=' ')]


import pandas as pd
df = pd.read_csv('data/fristons_twenty_four.1D',sep=' ',header=None)
motion_regressor = []
for i in df.columns:
    motion_regressor.append(df[i].tolist())



workflow = pe.Workflow(name= "level1")
workflow.base_dir = os.path.abspath('./workingdir')
workflow.config = {"execution": {"crashdump_dir":os.path.abspath('./crashdumps')}}
working_dir = os.path.join('/home/caroline/Documents/projects/fsl_estimate_workflow','working')



# Workflow base directory
if not os.path.isdir(working_dir):
    os.makedirs(working_dir)
workflow = pe.Workflow(name='no_smooth_no_derivs', base_dir=working_dir)

print 'create working dir '


#TODO data grabber
# Specify the location of the FEEDS data. You can find it at http://www.fmrib.ox.ac.uk/fsl/feeds/doc/index.html
feeds_data_dir = os.path.abspath('data')
# Specify the subject directories
# Map field names to individual subject runs.
info = dict(func=[['functional_nuisance_residuals']], struct=[['structural']])


datasource = pe.Node(interface=nio.DataGrabber(outfields=['func', 'struct']), name = 'datasource')
datasource.inputs.base_directory = feeds_data_dir
datasource.inputs.template = '%s.nii.gz'
datasource.inputs.template_args = info
datasource.inputs.sort_filelist = True

#smoothing
smooth = pe.Node(interface=spm.Smooth(), name="smooth")
smooth.inputs.fwhm = 4

#workflow.connect(datasource, "func", smooth, "in_files")
#preprocessing.connect(realign, "realigned_files", smooth, "in_files")

#modelspec
TR = 2
modelspec = pe.Node(interface=model.SpecifyModel(),name="modelspec")
modelspec.inputs.input_units = 'secs'
modelspec.inputs.time_repetition = TR
modelspec.inputs.high_pass_filter_cutoff = 100
modelspec.inputs.subject_info = [Bunch(conditions=['Control','Interference'],
                                onsets=[range(22,int(275),84),range(64,317,84)],
                                durations=[[42], [42]], regressors=None)]



workflow.connect(datasource, 'func', modelspec,'functional_runs')

#modelfit
modelfit = create_modelfit_workflow(name='ftest',f_contrasts=True)
modelfit.inputs.inputspec.interscan_interval = TR
modelfit.inputs.inputspec.model_serial_correlations = True
modelfit.inputs.inputspec.bases = {'dgamma': {'derivs': False}}
cont1 = ['Control>Baseline','T', ['Control','Interference'],[1,0]]
cont2 = ['Interference>Baseline','T', ['Control', 'Interference'],[0,1]]
cont4 = ['Interference>Control', 'T', ['Control', 'Interference'],[-1,1]]
cont5 = ['Control>Interference', 'T', ['Control', 'Interference'], [1,-1]]
cont3 = ['Task','F', [cont1,cont2]]

modelfit.inputs.inputspec.contrasts = [cont1, cont2, cont3, cont4, cont5]

workflow.connect(modelspec, 'session_info', modelfit, 'inputspec.session_info')
#workflow.connect(input_node, 'func', modelfit, 'inputspec.functional_data')
workflow.connect(datasource, 'func', modelfit, 'inputspec.functional_data')

#try
# fixedfx = create_fixed_effects_flow()
# workflow.connect(modelfit,'outputspec.copes', fixedfx, 'inputspec.copes')
# workflow.connect(modelfit,'outputspec.varcopes', fixedfx, 'inputspec.varcopes')
#end try




#try nipype registration instead of cpac
#write to standard space
mni = create_wf_apply_ants_warp(1,name='mni')
mni.inputs.inputspec.reference_image = template
mni.inputs.inputspec.dimension = 3
mni.inputs.inputspec.interpolation = 'Linear'

# # input_image_type:
# # (0 or 1 or 2 or 3)
# # Option specifying the input image type of scalar
# # (default), vector, tensor, or time series.
mni.inputs.inputspec.input_image_type = 3

# workflow.connect(modelfit,'outputspec.zfiles', mni, 'inputspec.input_image')



#smoothing
# smoothing = pe.MapNode(interface=fsl.MultiImageMaths(), name='smoothing', iterfield=['in_file'])
# smoothing.inputs.operand_files = template

# workflow.connect(mni, 'outputspec.output_image', smoothing, 'in_file')
# workflow.connect(modelfit, 'outputspec.copes', ds, 'image_files')


# from nipype.pipeline.plugins.callback_log import log_nodes_cb
# plugin_args = {'num_threads': 32, 'memory': 55.0, 'status_callback': log_nodes_cb, 
#     'memory_profile': False}

print 'ready to run'

workflow.run()
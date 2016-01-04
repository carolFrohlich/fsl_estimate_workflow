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


def download_input_file(sublist, sub_, aws_creds=None):

    # Import packages
    import os
    from CPAC.AWS import aws_utils, fetch_creds

    # Init variables
    bucket = None
    s3_str = 's3://'
    download_dir = os.path.join('/mnt', 'inputs')

    # Check if input file is on S3
    for datafile in sublist:
        if datafile.lower().startswith(s3_str):
            if not bucket:
                bname = datafile.split('/')[2]
                bucket = fetch_creds.return_bucket(aws_creds, bname)
            try:
                key = '/'.join(datafile.split('/')[3:])
                localfile = os.path.join(download_dir, key)
                if not os.path.exists(localfile):
                    aws_utils.s3_download(bucket, [key], download_dir)
            except Exception as exc:
                err_msg = 'There was a problem downloading: %s\nError: %s' \
                          % (datafile, exc)
                raise Exception(err_msg)

        else:
            localfile = datafile

        # Return local path
        return localfile



template = '/usr/share/fsl/5.0/data/standard/MNI152_T1_2mm_brain.nii.gz'

print 'start'
workflow = pe.Workflow(name= "level1")
workflow.base_dir = os.path.abspath('./workingdir')
workflow.config = {"execution": {"crashdump_dir":os.path.abspath('./crashdumps')}}
working_dir = os.path.join('/mnt','working')



# Workflow base directory
if not os.path.isdir(working_dir):
    os.makedirs(working_dir)
workflow = pe.Workflow(name='centrality_nfb8', base_dir=working_dir)

print 'create working dir '

# Init input node
sub_list = yaml.load(open('/home/ubuntu/sub8_preproc.yaml','rb'))

print 'read sublist'

input_node = pe.Node(util.Function(input_names=['sublist', 'sub_','aws_creds'],
                output_names=['localfile'], function=download_input_file),
                name='inputspec')



# Declare input as iterable
input_node.inputs.sublist = sub_list
input_node.iterables = ('sub_', [x[80:89] for x in sub_list])
input_node.inputs.aws_creds = '/home/ubuntu/cfroehlich-fcp-indi-keys.csv'


print 'set download node'

#modelspec
TR = 2
modelspec = pe.Node(interface=model.SpecifyModel(),name="modelspec")
modelspec.inputs.input_units = 'secs'
modelspec.inputs.time_repetition = TR
modelspec.inputs.high_pass_filter_cutoff = 100
modelspec.inputs.subject_info = [Bunch(conditions=['Control','Interference'],
                                onsets=[range(30,int(283),84),range(72,325,84)],
                                durations=[[42], [42]], regressors=None)]


workflow.connect(input_node, 'localfile', modelspec, 'functional_runs')

#modelfit
modelfit = create_modelfit_workflow(name='ftest',f_contrasts=True)
modelfit.inputs.inputspec.interscan_interval = TR
modelfit.inputs.inputspec.model_serial_correlations = True
modelfit.inputs.inputspec.bases = {'dgamma': {'derivs': True}}
cont1 = ['Control>Baseline','T', ['Control','Interference'],[1,0]]
cont2 = ['Interference>Baseline','T', ['Control', 'Interference'],[0,1]]
cont4 = ['Interference>Control', 'T', ['Control', 'Interference'],[-1,1]]
cont5 = ['Control>Interference', 'T', ['Control', 'Interference'], [1,-1]]
cont3 = ['Task','F', [cont1,cont2]]

modelfit.inputs.inputspec.contrasts = [cont1, cont2, cont3, cont4, cont5]

workflow.connect(modelspec, 'session_info', modelfit, 'inputspec.session_info')
workflow.connect(input_node, 'localfile', modelfit, 'inputspec.functional_data')



#write to standard space
mni = create_wf_apply_ants_warp(0,name='mni')
mni.inputs.inputspec.reference_image = template
mni.inputs.inputspec.dimension = 3
mni.inputs.inputspec.interpolation = 'Linear'

# input_image_type:
# (0 or 1 or 2 or 3)
# Option specifying the input image type of scalar
# (default), vector, tensor, or time series.
mni.inputs.inputspec.input_image_type = 3

workflow.connect(modelfit,'outputspec.copes', mni,'inputspec.input_image')



#smoothing
smoothing = pe.MapNode(interface=fsl.MultiImageMaths(), name='smoothing', iterfield=['in_file'])
smoothing.inputs.operand_files = template

workflow.connect(mni, 'outputspec.output_image', smoothing, 'in_file')


creds_path = '/home/ubuntu/cfroehlich-fcp-indi-keys.csv'

ds = pe.Node(nio.DataSink(), name='sinker')
ds.inputs.base_directory = 's3://fcp-indi/data/Projects/RocklandSample/Outputs/f-test'
ds.inputs.creds_path = creds_path

workflow.connect(modelfit, 'outputspec.copes', ds, 'image_files')


from nipype.pipeline.plugins.callback_log import log_nodes_cb
plugin_args = {'num_threads': 32, 'memory': 55.0, 'status_callback': log_nodes_cb, 
    'memory_profile': False}

print 'ready to run'

workflow.run(plugin='ResourceMultiProc', plugin_args=plugin_args)
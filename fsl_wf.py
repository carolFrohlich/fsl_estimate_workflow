import os                                    # system functions
import yaml
import nipype.interfaces.spm as spm          # spm
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


template = '/usr/share/fsl/5.0/data/standard/MNI152_T1_3mm_brain.nii.gz'


workflow = pe.Workflow(name= "level1")
workflow.base_dir = os.path.abspath('./workingdir')
workflow.config = {"execution": {"crashdump_dir":os.path.abspath('./crashdumps')}}
working_dir = os.path.abspath('./working')


# Workflow base directory
if not os.path.isdir(working_dir):
    os.makedirs(working_dir)
workflow = pe.Workflow(name='moralft', base_dir=working_dir)

# Specify the location of the data.
data_dir = os.path.abspath('data')
# Specify the subject directories
subject_list = ['A00028185','A00028352','A00033747','A00034854','A00035072','A00035827','A00035840','A00037112','A00037511','A00037848','A00038642','A00038998','A00039391','A00039431','A00040151','A00040193','A00040524','A00040573','A00040623','A00040628','A00040640','A00040944','A00043299','A00043520','A00043677','A00043704','A00043721','A00043722','A00043998','A00045590','A00050940','A00051539','A00051548','A00051676','A00051927','A00052125','A00052181','A00052340','A00052500','A00052560','A00053455','A00053473','A00053475','A00053850','A00053851','A00053902','A00054019','A00054441','A00054504','A00054857','A00054914','A00055121','A00055373','A00055446','A00055447','A00055542','A00055738','A00055763','A00055806','A00056097','A00056306','A00056452','A00056556','A00056627','A00056898','A00056949','A00057005','A00057035','A00057182','A00057203','A00057235','A00057372','A00057444','A00057786','A00057808','A00057965','A00058214','A00058218','A00058503','A00058552','A00058667','A00058952','A00058999','A00059344','A00059346','A00059428','A00059756','A00059845','A00059911','A00060006','A00060093','A00060169','A00060259','A00060279','A00060372','A00060407','A00060430','A00060471','A00060480','A00060516','A00060632','A00060848','A00060925','A00061204','A00061276','A00061387','A00061709','A00061806','A00062210','A00062248','A00062282','A00062288','A00062351','A00062917','A00062934','A00062942','A00063008','A00063103','A00063326','A00063368','A00063589','A00064081',]
#subject_list = ['A00035827','A00035840','A00037112']
# Map field names to individual subject runs.
info = dict(func=[['subject_id', ['moraldilemma_functional_mni']]], struct=[['subject_id','struct']])

infosource = pe.Node(interface=util.IdentityInterface(fields=['subject_id']), name="infosource")
infosource.iterables = ('subject_id', subject_list)

datasource = pe.Node(interface=nio.DataGrabber(infields=['subject_id'], outfields=['func', 'struct']),
                     name = 'datasource')
datasource.inputs.base_directory = data_dir
datasource.inputs.template = '%s/%s.nii.gz'
datasource.inputs.template_args = info
datasource.inputs.sort_filelist = True
workflow.connect(infosource, 'subject_id', datasource, 'subject_id')

#smoothing
def set_gauss(fwhm):
    fwhm = float(fwhm)
    sigma = float(fwhm / 2.3548)
    op = "-kernel gauss %f -fmean -mas " % (sigma) + "%s"
    op_string = op

    return op_string

smooth = pe.Node(interface=fsl.MultiImageMaths(), name="smooth")
smooth.inputs.op_string = set_gauss(6)
workflow.connect(datasource, "func", smooth, "in_file")
workflow.connect(datasource, "func", smooth, "operand_files")

#modelspec
TR = 2
##  msit
#modelspec = pe.Node(interface=model.SpecifyModel(),name="modelspec")
#modelspec.inputs.input_units = 'secs'
#modelspec.inputs.time_repetition = TR
#modelspec.inputs.high_pass_filter_cutoff = 100
#modelspec.inputs.subject_info = [Bunch(conditions=['Control','Interference'],
#                                 onsets=[range(22,int(275),84),range(64,317,84)],
#                                 durations=[[42], [42]], regressors=None)]
## end msit

##  moral dilemma
modelspec = pe.Node(interface=model.SpecifyModel(),name="modelspec")
modelspec.inputs.input_units = 'secs'
modelspec.inputs.time_repetition = TR
modelspec.inputs.high_pass_filter_cutoff = 100
modelspec.inputs.subject_info = [Bunch(conditions=['Control','Interference'],
                                onsets=[range(12,193,60),range(42,223,60)],
                                #(drop first 4 TRs) onsets=[range(20,201,60),range(50,231,60)],
                                durations=[[30], [30]], regressors=None)]
## end moral dilemma


#workflow.connect(datasource, 'func', modelspec,'functional_runs')
workflow.connect(smooth, 'out_file', modelspec,'functional_runs')


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

#workflow.connect(datasource, 'func', modelfit, 'inputspec.functional_data')
workflow.connect(smooth, 'out_file', modelfit, 'inputspec.functional_data')

workflow.run(plugin='MultiProc')

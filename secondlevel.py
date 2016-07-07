import glob
from nipype.interfaces.fsl import Merge

subjs = 0
for i in range(1,5):
    for t in ['cope', 'varcope']:
        base_dir = '/home2/cfroehlich/nfb3_preprocessed/working/moralft/ftest/*/modelestimate/mapflow/_modelestimate0/results/'+t+str(i)+'.nii.gz'
        x = glob.glob(base_dir)
        x.sort()
        x = [a for a in x if '0040628' not in a ]
        print x
        subjs = len(x)
        merger = Merge()
        merger.inputs.in_files = x
        merger.inputs.dimension = 't'
        merger.inputs.output_type = 'NIFTI_GZ'
        merger.run()

from nipype.interfaces.fsl import MultipleRegressDesign
model = MultipleRegressDesign()
model.inputs.contrasts = [['group mean', 'T',['reg1'],[1]]]
model.inputs.regressors = dict(reg1=[1]*subjs)
model.run()


from nipype.interfaces import fsl
import os
import shutil

for i in range(1,5):
  os.mkdir('./cope' + str(i))
  shutil.move('cope' + str(i) + '_merged.nii.gz','./cope' + str(i) + '/cope' + str(i) + '_merged.nii.gz')
  shutil.move('varcope' + str(i) + '_merged.nii.gz','./cope' + str(i) + '/varcope' + str(i) + '_merged.nii.gz')
  flameo = fsl.FLAMEO(cope_file='./cope' + str(i) + '/cope'+str(i)+'_merged.nii.gz',var_cope_file='./cope' + str(i) + '/varcope'+str(i)+'_merged.nii.gz',cov_split_file='design.grp',mask_file='/usr/share/fsl/5.0/data/standard/MNI152_T1_3mm_brain_mask.nii.gz',design_file='design.mat',t_con_file='design.con', run_mode='flame1')

  flameo.run()
  shutil.move('stats','./cope' + str(i))

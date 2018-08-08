#!/usr/bin/env python
#########################################################################################
#
# Perform various types of processing from the spinal cord segmentation (e.g. extract centerline, compute CSA, etc.).
# (extract_centerline) extract the spinal cord centerline from the segmentation. Output file is an image in the same
# space as the segmentation.
#
#
# ---------------------------------------------------------------------------------------
# Copyright (c) 2014 Polytechnique Montreal <www.neuro.polymtl.ca>
# Author: Benjamin De Leener, Julien Touati, Gabriel Mangeat
# Modified: 2014-07-20 by jcohenadad
#
# About the license: see the file LICENSE.TXT
#########################################################################################

# TODO: have file_out being by default the process name
# TODO: generalize "-o xxx" flag when used as a prefix file name (without extension):
# - centerline: xxx.csv (centerline coordinates as csv), xxx.nii.gz (centerline as binary nifti volume)
# - label-vert: xxx.nii.gz (labeled segmentation)
# - csa: xxx.csv (output csa values)
#   - other flags: -csa_volume xxx.nii.gz and -angle_volume xxx.nii.gz
# - shape: xxx.csv (output shape)
# - length: xxx.csv (spinal cord length)
# TODO: the import of scipy.misc imsave was moved to the specific cases (orth and ellipse) in order to avoid issue #62. This has to be cleaned in the future.

import sys, os
import sct_utils as sct
from msct_parser import Parser
from spinalcordtoolbox import process_seg


class Param:
    def __init__(self):
        self.debug = 0
        self.verbose = 1  # verbose
        self.remove_temp_files = 1
        self.slices = ''
        self.type_window = 'hanning'  # for smooth_centerline @sct_straighten_spinalcord
        self.window_length = 50  # for smooth_centerline @sct_straighten_spinalcord
        self.algo_fitting = 'hanning'  # nurbs, hanning


def get_parser():
    """
    :return: Returns the parser with the command line documentation contained in it.
    """
    # Initialize the parser
    parser = Parser(__file__)
    parser.usage.set_description(
        """This program is used to get the centerline of the spinal cord of a subject by using one of the three methods describe in the -method flag .""")
    parser.add_option(name='-i',
                      type_value='image_nifti',
                      description='Spinal Cord segmentation',
                      mandatory=True,
                      example='seg.nii.gz')
    parser.add_option(name='-p',
                      type_value='multiple_choice',
                      description='type of process to be performed:\n'
                                  '- centerline: extract centerline as binary file.\n'
                                  '- label-vert: Transform segmentation into vertebral level using a file that contains labels with disc value (flag: -discfile)\n'
                                  '- length: compute length of the segmentation.\n'
                                  '- csa: computes cross-sectional area by counting pixels in each'
                                  '  slice and then geometrically adjusting using centerline orientation. Note that it '
                                  '  is possible to input a binary mask or a mask comprising values within the range '
                                  '  [0,1] to account for partial volume effect. Default output file is: ./csa.csv'
                                  '- shape: compute spinal shape properties, using scikit-image region measures, including:\n'
                                  '  - AP and RL diameters\n'
                                  '  - ratio between AP and RL diameters\n'
                                  '  - spinal cord area\n'
                                  '  - eccentricity: Eccentricity of the ellipse that has the same second-moments as the spinal cord. The eccentricity is the ratio of the focal distance (distance between focal points) over the major axis length. The value is in the interval [0, 1). When it is 0, the ellipse becomes a circle.\n'
                                  '  - equivalent diameter: The diameter of a circle with the same area as the spinal cord.\n'
                                  '  - orientation: angle (in degrees) between the AP axis of the spinal cord and the AP axis of the image\n'
                                  '  - solidity: ratio of positive (spinal cord) over null (background) pixels that are contained in the convex hull region. The convex hull region is the smallest convex polygon that surround all positive pixels in the image.',
                      mandatory=True,
                      example=['centerline', 'label-vert', 'length', 'csa', 'shape'])
    parser.usage.addSection('Optional Arguments')
    parser.add_option(name='-o',
                      type_value='file_output',
                      description="Output file name (add extension). Ex: my_csa.csv (with -p csa).",
                      mandatory=False)
    parser.add_option(name="-ofolder",
                      type_value="str",
                      description="Deprecated. Please use -o.",
                      mandatory=False)
    parser.add_option(name='-overwrite',
                      type_value='int',
                      description="""In the case you specified, in flag \"-ofolder\", a pre-existing folder that already includes a .xls result file (see flags \"-p csa\" and \"-z\" or \"-vert\"), this option will allow you to overwrite the .xls file (\"-overwrite 1\") or to add the results to it (\"-overwrite 0\").""",
                      mandatory=False,
                      default_value=0)
    parser.add_option(name='-z',
                      type_value='str',
                      description='Slice range to compute the CSA across (requires \"-p csa\").',
                      mandatory=False,
                      example='5:23')
    parser.add_option(name='-perslice',
                      type_value='int',
                      description='Set to 1 to output one metric per slice instead of a single output metric.'
                                  'Please note that when methods ml or map is used, outputing a single '
                                  'metric per slice and then averaging them all is not the same as outputting a single'
                                  'metric at once across all slices.',
                      mandatory=False,
                      default_value=0)
    parser.add_option(name='-vert',
                      type_value='str',
                      description='Vertebral levels to compute the CSA across (requires \"-p csa\"). Example: 2:9 for C2 to T2.',
                      mandatory=False,
                      example='2:9')
    parser.add_option(name='-vertfile',
                      type_value='str',
                      description='Vertebral labeling file. Only use with flag -vert',
                      default_value='./label/template/PAM50_levels.nii.gz',
                      mandatory=False)
    parser.add_option(name='-perlevel',
                      type_value='int',
                      description='Set to 1 to output one metric per vertebral level instead of a single '
                                  'output metric.',
                      mandatory=False,
                      default_value=0)
    parser.add_option(name='-discfile',
                      type_value='image_nifti',
                      description='Disc labeling with the convention "disc labelvalue=3 ==> disc C2/C3". Only use with -p label-vert',
                      mandatory=False)
    parser.add_option(name='-r',
                      type_value='multiple_choice',
                      description='Removes the temporary folder and debug folder used for the algorithm at the end of execution',
                      mandatory=False,
                      default_value='1',
                      example=['0', '1'])
    parser.add_option(name='-size',
                      type_value='int',
                      description='Window size (in mm) for smoothing CSA. 0 for no smoothing.',
                      mandatory=False,
                      default_value=0)
    parser.add_option(name='-a',
                      type_value='multiple_choice',
                      description='Algorithm for curve fitting.',
                      mandatory=False,
                      default_value='nurbs',
                      example=['hanning', 'nurbs'])
    parser.add_option(name='-no-angle',
                      type_value='multiple_choice',
                      description='0: angle correction for csa computation. 1: no angle correction. When angle '
                                  'correction is used, the CSA is calculated within the slice by computing the surface '
                                  'of the segmentation, and then correcting the CSA by the cosine of the angle between '
                                  'the slice plane and the cord centerline (previously estimated using a regularized '
                                  'NURBS function). With the flag -no-angle 1, no correction is applied, which is '
                                  'usually correct for data acquired orthogonally to the cord.',
                      mandatory=False,
                      example=['0', '1'],
                      default_value='0')
    parser.add_option(name='-use-image-coord',
                      type_value='multiple_choice',
                      description='0: physical coordinates are used to compute CSA. 1: image coordinates are used to compute CSA.\n'
                                  'Physical coordinates are less prone to instability in CSA computation and should be preferred.',
                      mandatory=False,
                      example=['0', '1'],
                      default_value='0')
    parser.add_option(name='-v',
                      type_value='multiple_choice',
                      description='1: display on, 0: display off (default)',
                      mandatory=False,
                      example=['0', '1', '2'],
                      default_value='1')
    parser.add_option(name='-h',
                      type_value=None,
                      description='display this help',
                      mandatory=False)

    return parser


def main(args):
    parser = get_parser()
    arguments = parser.parse(args)
    param = Param()

    # Initialization
    slices = param.slices
    angle_correction = True
    use_phys_coord = True

    fname_segmentation = arguments['-i']
    name_process = arguments['-p']
    overwrite = 0
    fname_vert_levels = ''
    if '-o' in arguments:
        file_out = os.path.abspath(arguments['-o'])
    else:
        file_out = ''
    if "-ofolder" in arguments:
        sct.printv('The flag "-ofolder" is deprecated. Please use -o. Exiting.', 1, 'error')
    if '-overwrite' in arguments:
        overwrite = arguments['-overwrite']
    if '-vert' in arguments:
        vert_levels = arguments['-vert']
    else:
        vert_levels = ''
    if '-r' in arguments:
        remove_temp_files = arguments['-r']
    if '-vertfile' in arguments:
        fname_vert_levels = arguments['-vertfile']
    if '-perlevel' in arguments:
        perlevel = arguments['-perlevel']
    else:
        perlevel = 0
    if '-v' in arguments:
        verbose = int(arguments['-v'])
    if '-z' in arguments:
        slices = arguments['-z']
    if '-perslice' in arguments:
        perslice = arguments['-perslice']
    else:
        perslice = 0
    if '-a' in arguments:
        param.algo_fitting = arguments['-a']
    if '-no-angle' in arguments:
        if arguments['-no-angle'] == '1':
            angle_correction = False
        elif arguments['-no-angle'] == '0':
            angle_correction = True
    if '-use-image-coord' in arguments:
        if arguments['-use-image-coord'] == '1':
            use_phys_coord = False
        if arguments['-use-image-coord'] == '0':
            use_phys_coord = True

    # update fields
    param.verbose = verbose

    # update file_out with name of process
    if not file_out:
        file_out = name_process

    if name_process == 'centerline':
        process_seg.extract_centerline(fname_segmentation, remove_temp_files, verbose=param.verbose,
                                       algo_fitting=param.algo_fitting, use_phys_coord=use_phys_coord,
                                       file_out=file_out)

    if name_process == 'csa':
        process_seg.compute_csa(fname_segmentation, overwrite, verbose, remove_temp_files, slices,
                                vert_levels, fname_vert_levels=fname_vert_levels, perslice=perslice,
                                perlevel=perlevel, algo_fitting=param.algo_fitting,
                                type_window=param.type_window, window_length=param.window_length,
                                angle_correction=angle_correction, use_phys_coord=use_phys_coord,
                                file_out=file_out)

    if name_process == 'label-vert':
        if '-discfile' in arguments:
            fname_discs = arguments['-discfile']
        else:
            sct.printv('\nERROR: Disc label file is mandatory (flag: -discfile).\n', 1, 'error')
        process_seg.label_vert(fname_segmentation, fname_discs, file_out=file_out, verbose=verbose)

    if name_process == 'length':
        process_seg.compute_length(fname_segmentation, remove_temp_files, output_folder, overwrite, slices,
                                   vert_levels, fname_vert_levels, verbose=verbose)

    if name_process == 'shape':
        fname_discs = None
        if '-discfile' in arguments:
            fname_discs = arguments['-discfile']
        process_seg.compute_shape(fname_segmentation, slices=slices, vert_levels=vert_levels,
                                  fname_vert_levels=fname_vert_levels, perslice=perslice, perlevel=perlevel,
                                  file_out=file_out, overwrite=overwrite, remove_temp_files=remove_temp_files,
                                  verbose=verbose)


if __name__ == "__main__":
    sct.init_sct()
    # initialize parameters
    param = Param()
    param_default = Param()
    # call main function
    main(sys.argv[1:])

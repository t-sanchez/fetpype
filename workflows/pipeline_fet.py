import sys
import os
import nipype.pipeline.engine as pe
from fetpype.pipelines.full_pipeline import (
    create_full_pipeline,
)
from fetpype.utils.utils_bids import (
    create_datasource,
    create_datasink,
    create_bids_datasink,
    create_description_file,
)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils import (  # noqa: E402
    get_default_parser,
    init_and_load_cfg,
    check_and_update_paths,
    get_pipeline_name,
    check_valid_pipeline,
)

###############################################################################

__file_dir__ = os.path.dirname(os.path.abspath(__file__))


def create_main_workflow(
    data_dir,
    out_dir,
    nipype_dir,
    subjects,
    sessions,
    acquisitions,
    cfg_path,
    nprocs,
    save_intermediates=False,
):
    """
    Instantiates and runs the entire workflow of the fetpype pipeline.

    Args:
        data_dir (str):
            Path to the BIDS directory that contains anatomical images.
        out_dir (str):
            Path to the output directory (will be created if not already
            existing). Previous outputs may be overriden.
        nipype_dir (str):
            Path to the nipype directory.
        subjects (list[str], optional):
            List of subject IDs matching the BIDS specification
            (e.g., sub-[SUB1], sub-[SUB2], ...).
        sessions (list[str], optional):
            List of session IDs matching the BIDS specification
            (e.g., ses-[SES1], ses-[SES2], ...).
        acquisitions (list[str], optional):
            List of acquisition names matching the BIDS specification
            (e.g., acq-[ACQ1], ...).
        cfg_path (str):
            Path to a hydra  configuration file (YAML) specifying pipeline
            parameters.
        nprocs (int):
            Number of processes to be launched by MultiProc.

    """

    cfg = init_and_load_cfg(cfg_path, __file_dir__)
    data_dir, out_dir, nipype_dir = check_and_update_paths(
        data_dir, out_dir, nipype_dir, cfg
    )
    # Print the three paths
    print(f"Data directory: {data_dir}")
    print(f"Output directory: {out_dir}")
    print(f"Nipype directory: {nipype_dir}")

    check_valid_pipeline(cfg)
    # if general, pipeline is not in params ,create it and set it to niftymic

    # main_workflow
    main_workflow = pe.Workflow(name=get_pipeline_name(cfg))
    main_workflow.base_dir = nipype_dir
    fet_pipe = create_full_pipeline(cfg)

    output_query = {
        "stacks": {
            "datatype": "anat",
            "suffix": "T2w",
            "extension": ["nii", ".nii.gz"],
        }
    }

    # datasource
    datasource = create_datasource(
        output_query,
        data_dir,
        subjects,
        sessions,
        acquisitions,
    )

    # in both cases we connect datsource outputs to main pipeline
    main_workflow.connect(datasource, "stacks", fet_pipe, "inputnode.stacks")

    # Get subject, session and acquisition IDs from the datasource 
    # subject_ids, session_ids, acq_ids = zip(*datasource.iterables[1])
    # subject_ids, session_ids, acq_ids = list(subject_ids), list(session_ids), list(acq_ids)

    # Reconstruction data sink:
    pipeline_name = get_pipeline_name(cfg)
    desc_file = create_description_file(
        out_dir, pipeline_name, cfg=cfg
    )

    # Preprocessing data sink:
    if save_intermediates:
        datasink_path_intermediate = os.path.join(out_dir, "preprocessing")
        os.makedirs(datasink_path_intermediate, exist_ok=True)
        create_description_file(
            datasink_path_intermediate, "preprocessing", cfg=cfg.reconstruction
        )

        # Create a datasink for the preprocessing pipeline
        preprocessing_datasink_denoised = create_bids_datasink(
            out_dir=datasink_path_intermediate,
            pipeline_name="preprocessing",  # Use combined name
            strip_dir=main_workflow.base_dir,
            name="preprocessing_datasink_denoised",
            desc_label="denoised",
        )
        preprocessing_datasink_masked = create_bids_datasink(
            out_dir=datasink_path_intermediate,
            pipeline_name="preprocessing",  # Use combined name
            strip_dir=main_workflow.base_dir,
            name="preprocessing_datasink_cropped",
            desc_label="cropped",
        )

        # Connect the pipeline to the datasinks
        main_workflow.connect(
            fet_pipe, "Preprocessing.outputnode.stacks", preprocessing_datasink_denoised, "@stacks"
        )
        main_workflow.connect(
            fet_pipe, "Preprocessing.outputnode.masks", preprocessing_datasink_masked, "@masks"
        )
    
    recon_datasink = create_bids_datasink(
        out_dir=out_dir,
        pipeline_name=pipeline_name,
        strip_dir=main_workflow.base_dir,
        name="final_recon_datasink",
        rec_label=cfg.reconstruction.pipeline,
    )

    # Create another datasink for the segmentation pipeline
    seg_datasink = create_bids_datasink(
        out_dir=out_dir,
        pipeline_name=pipeline_name,
        strip_dir=main_workflow.base_dir,
        name="final_seg_datasink",
        rec_label=cfg.reconstruction.pipeline,
        seg_label=cfg.segmentation.pipeline,
    )

    # Connect the pipeline to the datasink
    main_workflow.connect(
        fet_pipe, "outputnode.output_srr", recon_datasink, f"@{pipeline_name}"
    )
    main_workflow.connect(
        fet_pipe, "outputnode.output_seg", seg_datasink, f"@{cfg.segmentation.pipeline}"
    )

    if cfg.save_graph:
        main_workflow.write_graph(
            graph2use="colored",
            format="png",
            simple_form=True,
        )

    main_workflow.config["execution"] = {"remove_unnecessary_outputs": "false"}
    main_workflow.run(plugin="MultiProc", plugin_args={"n_procs": nprocs})


def main():
    # import logging

    # # Get the specific logger for Nipype interfaces
    # if_logger = logging.getLogger('nipype.interface')
    # if_logger.setLevel(logging.DEBUG)

    # # Optional: Also set the workflow logger level if needed
    # wf_logger = logging.getLogger('nipype.workflow')
    # wf_logger.setLevel(logging.DEBUG)

    # # Optional: Configure basic logging to print to console
    # # This might already be happening, but ensures messages are shown
    # logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # Command line parser
    parser = get_default_parser(
        "Run the entire Fetpype pipeline -- "
        "pre-processing, reconstruction and segmentation"
    )

    args = parser.parse_args()

    # main_workflow
    print("Initialising the pipeline...")
    create_main_workflow(
        data_dir=args.data,
        out_dir=args.out,
        nipype_dir=args.nipype_dir,
        subjects=args.sub,
        sessions=args.ses,
        acquisitions=args.acq,
        cfg_path=args.cfg_path,
        nprocs=args.nprocs,
        save_intermediates=args.save_intermediates,
    )


if __name__ == "__main__":
    main()
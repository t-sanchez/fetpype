def run_seg_cmd(input_srr, cmd, cfg):
    from fetpype.nodes.utils import (
        is_valid_cmd,
        get_directory,
        get_mount_docker,
    )
    import os
    import numpy as np
    import nibabel as nib

    VALID_TAGS = [
        "mount",
        "input_vol",
        "input_dir",
        "output_dir",
        "output_seg",
    ]
    is_valid_cmd(cmd, VALID_TAGS)

    # Copy input_srr to input_directory -- Avoid mounting problematic directories
    input_srr_dir = os.path.join(os.getcwd(), "seg/input")
    os.makedirs(input_srr_dir, exist_ok=True)
    os.system(f"cp {input_srr} {input_srr_dir}/input_srr.nii.gz")
    input_srr = os.path.join(input_srr_dir, "input_srr.nii.gz")

    output_dir = os.path.join(os.getcwd(), "seg/out")
    seg = os.path.join(output_dir, "seg.nii.gz")

    # In cmd, there will be things contained in <>.
    # Check that everything that is in <> is in valid_tags
    # If not, raise an error

    # Replace the tags in the command
    cmd = cmd.replace("<input_srr>", input_srr)
    cmd = cmd.replace("<input_dir>", input_srr_dir)
    cmd = cmd.replace("<output_seg>", seg)
    if "<output_dir>" in cmd:
        cmd = cmd.replace("<output_dir>", output_dir)
        # Assert that args.path_to_output is defined
        assert (
            cfg.path_to_output is not None
        ), "<output_dir> found in the command of reconstruction, but path_to_output is not defined."

        seg = os.path.join(output_dir, cfg.path_to_output)
        if "<basename>" in seg:
            seg = seg.replace("<basename>", os.path.basename(input_srr))
    if "<mount>" in cmd:
        mount_cmd = get_mount_docker(input_srr_dir, output_dir)
        cmd = cmd.replace("<mount>", mount_cmd)
    print(f"Running command:\n {cmd}")
    os.system(cmd)
    return seg

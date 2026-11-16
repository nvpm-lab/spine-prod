# Summary of ProtoDUNE-SP full chain configurations and their characteristics

**NOTE: These configurations use a modular YAML include system. See the "Configuration Structure" section below for details.**

The configurations below are for ProtoDUNE-SP datasets. This summary is divided by training/validation dataset and configuration version.

## Configuration Structure

All ProtoDUNE-SP configs use a **hierarchical YAML include system** with composable components:

### Main Configurations
- **`full_chain_261116.yaml`**: November 2026 full chain (260906 model) with
  track-aware recombination in post-processing
- **`full_chain_260906.yaml`**: September 2026 full chain trained on mpvmpr v1
- **`full_chain_260210.yaml`**: February 2026 full chain trained on mpvmpr v0

### Component Structure
Each main config includes modular YAML files:

**Base Components:**
- **`base/base_260210.yaml`**: Geometry and base settings (Feb 2026)
- **`base/base_common.yaml`**: Common base configuration

**IO Components:**
- **`io/io_260210.yaml`**: IO configuration (Feb 2026)
- **`io/io_common.yaml`**: Common IO settings

**Model Components:**
- **`model/model_260906.yaml`**: September 2026 mpvmpr v1 model and published checkpoint
- **`model/model_260210.yaml`**: Feb 2026 weights and model settings
- **`config/model/protodune-sp/full_chain/model_260906.yaml`**: Shared mpvmpr v1 architecture
- **`config/model/protodune-sp/full_chain/model_260210.yaml`**: Shared dated
  architecture used by inference, training caches, testing and weight export

**Post-processing Components:**
- **`post/post_261116.yaml`**: Post-processing with track-aware Modified Box
  recombination (Nov 2026)
- **`post/post_260210.yaml`**: Post-processing configuration (Feb 2026)
- **`post/post_common.yaml`**: Common post-processing settings

### Modifiers
Located in `modifier/` subdirectories:
- **`data/mod_data_261116.yaml`**: Data-only mode with the collection-plane data
  gain in-chain and in the post-processing recalibration (requires post >= 261116)
- **`data/mod_data_260906.yaml`**: Data-only mode with the updated collection-plane gain
- **`data/mod_data_260210.yaml`**: Data-only mode (no truth labels)
- **`lite/mod_lite_260210.yaml`**: Lite mode (reduced output)

### Legacy Configs
No legacy configs are present in this directory. Add legacy YAML configs to a `legacy/` subdirectory if needed for backward compatibility.

## Configurations for MPV/MPR v00

These weights have been trained/validated using the following files:
- Training set: `/sdf/data/neutrino/pdune/sim/sp/mpvmpr_v0/train_file_list.txt`
- Test set: `/sdf/data/neutrino/pdune/sim/sp/mpvmpr_v0/test_file_list.txt`

Known issue(s):
  - Poorly tuned ghost labeling
  - No charged kaon in the sample

## February 10th 2026

```shell
full_chain_260210.yaml
```

Description:
  - UResNet + PPN + gSPICE + GrapPAs (track + shower + interaction)
  - Modular YAML structure with base/io/model/post components
  - Original mpvmpr v0 production configuration

Known issue(s):
  - No charged kaon in the training sample

*For more details on each component, see the corresponding YAML files in the subdirectories.*

## September 6th 2026

```shell
full_chain_260906.yaml
```

Description:
  - Full six-module chain trained through the staged mpvmpr v1 pipeline
  - Updated calibration, Graph-SPICE geometry, track aggregation and interaction objectives
  - Published six-class PID checkpoint with charged-kaon support

## November 16th 2026

```shell
full_chain_261116.yaml
```

Description:
  - Same model, weights and in-chain calibration as `full_chain_260906.yaml`
  - New post-processing bundle `post/post_261116.yaml`: a `calibration` stage
    before `calo_ke` recalibrates reconstructed depositions from the preserved
    input charge (`depositions_q`) with tracking enabled. Each track is cut into
    `bin_pca` segments, and each segment is corrected with the inverse Modified
    Box factor of its own lifetime-corrected dQ/dx (stage order gain -> lifetime
    -> recombination). Segments with too few points, showers, and points not
    assigned to a particle keep the flat MIP correction.
  - Same Modified Box parameters as in-chain (ICARUS, alpha = 0.906,
    beta = 0.203, E = 0.4867 kV/cm), so the MIP energy scale is unchanged
  - For data, use `modifier/data/mod_data_261116.yaml`, which also sets the
    data gain in the post-processing calibration

Motivation:
  - The in-chain calibration runs before clustering, so it can only apply the
    flat MIP recombination factor. For heavily ionising tracks this
    underestimates the deposited energy by the ratio R(dE/dx) / R_MIP: 0.91 at
    4 MeV/cm, 0.81 at 6 MeV/cm, 0.73 at 8 MeV/cm, 0.62 at 12 MeV/cm

Known issue(s):
  - Requires a SPINE runtime with the track-aware recombination fix for
    degenerate segments. SPINE 1.4.5 crashes on tracks with a single point in
    a TPC, and points left out of every segment are not initialised.
  - Only removes the flat-recombination bias; stopping protons still show a
    calorimetric energy deficit relative to range (studied separately)

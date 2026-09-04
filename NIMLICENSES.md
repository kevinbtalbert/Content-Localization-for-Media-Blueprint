# NVIDIA NIM Licenses

This project uses the following NVIDIA NIM (NVIDIA Inference Microservices) containers. Each NIM is subject to its own license terms as described below.

## LipSync NIM


|                 |                                                                                                                                                                                                                                                                                           |
| --------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Name**        | NVIDIA LipSync NIM                                                                                                                                                                                                                                                                        |
| **Image**       | `nvcr.io/nim/nvidia/lipsync:latest`                                                                                                                                                                                                                                                       |
| **NGC**         | [https://catalog.ngc.nvidia.com/orgs/nim/teams/nvidia/containers/lipsync](https://catalog.ngc.nvidia.com/orgs/nim/teams/nvidia/containers/lipsync)                                                                                                                                        |
| **License**     | [NVIDIA Software License Agreement](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-software-license-agreement/), [Product-Specific Terms for NVIDIA AI Products](https://www.nvidia.com/en-us/agreements/enterprise-software/product-specific-terms-for-ai-products/) |
| **Description** | Synchronizes lip movements in video with translated audio.                                                                                                                                                                                                                                |


## Active Speaker Detection (ASD) NIM


|                 |                                                                                                                                                                                                                                                                                           |
| --------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Name**        | NVIDIA Active Speaker Detection NIM                                                                                                                                                                                                                                                       |
| **Image**       | `nvcr.io/nim/nvidia/active-speaker-detection:latest`                                                                                                                                                                                                                                      |
| **NGC**         | [https://catalog.ngc.nvidia.com/orgs/nim/teams/nvidia/containers/active-speaker-detection](https://catalog.ngc.nvidia.com/orgs/nim/teams/nvidia/containers/active-speaker-detection)                                                                                                      |
| **License**     | [NVIDIA Software License Agreement](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-software-license-agreement/), [Product-Specific Terms for NVIDIA AI Products](https://www.nvidia.com/en-us/agreements/enterprise-software/product-specific-terms-for-ai-products/) |
| **Description** | Detects which speakers are actively speaking in a video for speaker-aware dubbing.                                                                                                                                                                                                        |


---

**Note**: These NIMs are not distributed as part of this open-source project. They are subject to NVIDIA license terms on NGC.

### Baked model weights in the ContentLocalization runtime image

The CAI build path **embeds LipSync and ASD model artifacts** inside the runtime image (see `build/nim-model-cache/` and [cai/README.md](cai/README.md)). That means:

1. **Who builds the image** must hold a valid **NGC API key** with entitlement to pull the LipSync and ASD NIM images and model weights from `nvcr.io` (including [NVIDIA AI for Media Private Access](https://developer.nvidia.com/ai-for-media/private-access-program) for LipSync).
2. **Who deploys or uses the built image** must **independently** hold NVIDIA NIM licensing / NGC entitlement for those models. Baking weights into an image does **not** transfer or substitute for a customer’s license.
3. **Do not distribute** a runtime image containing baked NIM weights to parties who lack the applicable NVIDIA agreements.

Users accept NVIDIA license terms when accessing these containers and models from NGC. See the license links in the tables above.

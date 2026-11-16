# Third-party notices

## Local image model

Xortify's optional prototype image model is MediaPipe EfficientNet-Lite0 ImageNet 224 INT8/UINT8 ONNX, converted and published by KETI Software Platform Team:

- Model card and license: https://huggingface.co/ketiswp/mediapipe-EfficientNet-Lite0-ImageNet-224-int8-uint8-onnx
- Downloaded file: model.onnx
- Expected size: 5,148,096 bytes
- SHA-256: bd61897fc7744478bd42bb7714ed22769cc0bf05a0980c9ce03dcf48cace26bc
- License declared by the model card: Apache License 2.0

Xortify downloads this artifact only after the user requests it. It verifies the expected size and SHA-256 before installation. The model is not sent to a cloud inference service.

### Commercial-use review required

The converted model card's Apache 2.0 label covers the published model artifact. It does not resolve the separate terms of its training dataset. The official ImageNet access agreement describes use of its database for non-commercial research and educational purposes. The weights and data terms need a qualified commercial-use review before Xortify sells or redistributes this model. If adequate rights cannot be confirmed, the product release must use a replacement model and dataset with commercially cleared terms.

- ImageNet access terms: https://image-net.org/accessagreement
- ImageNet usage overview: https://image-net.org/about.php

## Image label names

The 1,001-line label map in src/xortify/assets/imagenet_labels.txt comes from the Google AI Edge MediaPipe Image Classifier label asset:

- Source: https://storage.googleapis.com/mediapipe-tasks/image_classifier/labels.txt
- Documentation: https://developers.google.com/edge/mediapipe/solutions/vision/image_classifier

The label map's first entry is a background label; the 1,000 remaining entries align with the model outputs. Preserve this attribution in redistributed builds and re-check the asset terms before commercial release.

## Runtime libraries

The optional vision extra uses NumPy, ONNX Runtime, and Pillow. Each dependency retains its own license and notices when included in a packaged application. PySide6 also has its own LGPL/GPL/commercial licensing terms. Packaging and distribution review should inventory the exact wheels, Qt plugins, codecs, and licenses included in the final Windows installer.

The Android build uses ONNX Runtime Android 1.23.2 (`com.microsoft.onnxruntime:onnxruntime-android`) under its Apache 2.0 license, plus AndroidX and Jetpack Compose libraries. Preserve their license notices when creating a release build and inventory the native libraries included for each Android ABI.

## Product release checklist

Before any paid distribution, record:

1. The model artifact's exact revision and license text.
2. Training data provenance and commercial permissions.
3. Label-map attribution and license.
4. The exact dependency and Qt plugin licenses in the built installer.
5. Any changes to these assets or their upstream terms.
6. The Android runtime's Apache notice and the final APK's ABI-specific native libraries.

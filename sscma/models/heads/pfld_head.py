# Copyright (c) Seeed Technology Co.,Ltd. All rights reserved.
from typing import Sequence, Union

import torch
import torch.nn as nn

from mmengine import MODELS
from ..base.general import CBR


def pose_acc(pred, target, hw, th=10):
    h = hw[0] if isinstance(hw[0], int) else int(hw[0][0])
    w = hw[1] if isinstance(hw[1], int) else int(hw[1][0])
    pred[:, 0::2] = pred[:, 0::2] * w
    pred[:, 1::2] = pred[:, 1::2] * h
    pred[pred < 0] = 0

    target[:, 0::2] = target[:, 0::2] * w
    target[:, 1::2] = target[:, 1::2] * h

    th = th
    acc = []
    for p, t in zip(pred, target):
        distans = ((t[0] - p[0]) ** 2 + (t[1] - p[1]) ** 2) ** 0.5
        if distans > th:
            acc.append(0)
        elif distans > 1:
            acc.append((th - distans) / (th - 1))
        else:
            acc.append(1)
    return sum(acc) / len(acc)


def audio_acc(pred, target):
    pred = (
        pred[0] if len(pred.shape) == 2 else pred
    )  # onnx shape(d,), tflite shape(1,d)
    pred = pred.argsort()[::-1][:5]
    correct = (target == pred).astype(float)
    acc = (correct[0], correct.max())  # (top1, top5) accuracy

    return acc


class PFLDhead(nn.Module):
    """The head of the pfld model mainly uses convolution and global average
    pooling.

    Args:
        num_point: The model needs to predict the number of key points,
            and set the output of the model according to this value
        input_channel: The number of channels of the head input feature map
        feature_num: Number of channels in the middle feature map of the head
        act_cfg: Configuration of the activation function
        loss_cfg: Related configuration of model loss function
    """

    def __init__(
        self,
        num_point: int = 1,
        input_channel: int = 320,
        feature_num: Sequence[int] = [32, 32],
        act_cfg: Union[dict, str, None] = "ReLU",
        loss_cfg: dict = dict(type="PFLDLoss"),
    ) -> None:
        super().__init__()

        self.conv1 = CBR(
            input_channel, feature_num[0], 3, 2, padding=1, bias=False, act=act_cfg
        )
        self.conv2 = CBR(
            feature_num[0], feature_num[1], 2, 1, bias=False, padding=0, act=act_cfg
        )

        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.fc = nn.Linear(input_channel + sum(feature_num), num_point * 2)
        self.lossFunction = MODELS.build(loss_cfg)

    def forward(self, x):
        if isinstance(x, (list, tuple)):
            x = x[0]

        x1 = self.avg_pool(x)
        x1 = x1.view(x1.size(0), -1)

        x = self.conv1(x)
        x2 = self.avg_pool(x)
        x2 = x2.view(x2.size(0), -1)

        x3 = self.conv2(x)
        x3 = self.avg_pool(x3)
        x3 = x3.view(x3.size(0), -1)

        multi_scale = torch.cat([x1, x2, x3], 1)

        landmarks = self.fc(multi_scale)

        return landmarks

    def loss(self, features, data_samples):
        preds = self.forward(features)
        labels = torch.as_tensor(
            data_samples["keypoints"], device=preds.device, dtype=torch.float32
        )
        loss = self.lossFunction(preds, labels)
        acc = pose_acc(preds, labels, data_samples["hw"])
        return {"loss": loss, "Acc": torch.as_tensor(acc, dtype=torch.float32)}

    def predict(self, features):
        return self.forward(features)

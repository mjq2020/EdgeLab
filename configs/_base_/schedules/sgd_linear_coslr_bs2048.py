from mmengine.optim import LinearLR
from mmengine.optim import CosineAnnealingLR
from torch.optim import SGD

# optimizer
# In ClassyVision, the lr is set to 0.003 for bs4096.
# In this implementation(bs2048), lr = 0.003 / 4096 * (32bs * 64gpus) = 0.0015
optim_wrapper = dict(
    optimizer=dict(type=SGD, lr=0.01, weight_decay=0.0005, momentum=0.937),
    # specific to vit pretrain
    paramwise_cfg=dict(
        custom_keys={
            ".cls_token": dict(decay_mult=0.0),
            ".pos_embed": dict(decay_mult=0.0),
        }
    ),
)

# learning policy
warmup_epochs = 3  # about 10000 iterations for ImageNet-1k
param_scheduler = [
    # warm up learning rate scheduler
    dict(
        type=LinearLR,
        start_factor=0.3333,
        by_epoch=True,
        begin=0,
        end=warmup_epochs,
        # update by iter
        convert_to_iter_based=True,
    ),
    # main learning rate scheduler
    dict(type=CosineAnnealingLR, eta_min=0.0002, by_epoch=True, begin=warmup_epochs),
]

# train, val, test setting
train_cfg = dict(by_epoch=True, max_epochs=100, val_interval=1)
val_cfg = dict()
test_cfg = dict()

# NOTE: `auto_scale_lr` is for automatically scaling LR,
# based on the actual training batch size.
auto_scale_lr = dict(base_batch_size=2048)

> LaSOT

```shell
python3 tools/test.py unicorn_sot ${exp_name} --dataset lasot --threads 32
python3 tools/analysis_results.py --name ${exp_name}
```
`${exp_name}` 表示 `exps/default` 对应的 `python` 文件名称！注意和 `model_zoo.md` 中的权重对应起来，`tracking` 预训练模型都带有 `mask` 参数！

示例：
```
python3 tools/test.py unicorn_sot unicorn_track_tiny_mask --dataset lasot --threads 8
```
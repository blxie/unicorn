> `torch` 版本

-   `CUDA 11.3`
-   `Python 3.7`
-   `Pytorch 1.10.0`
    https://pytorch.org/get-started/previous-versions/
    注意去掉最后的 `-c conda-forge`！！！

> 自定义安装

```shell
conda create -n unicorn python=3.9
conda activate unicorn

conda install pytorch==1.10.1 torchvision==0.11.2 torchaudio==0.10.1 cudatoolkit=11.3 -c pytorch  # 注意去掉最后的 -c conda-forge ！！！
# YOLOX and some other packages
pip3 install -U pip && pip3 install -r requirements.txt
python3 setup.py develop  # 注意不要使用 install !!! 注册 unicorn 到环境中

# Install Deformable Attention
cd unicorn/models/ops
bash make.sh
cd ../../..

# Install mmcv, mmdet, bdd100k
cd external/qdtrack
# mmcv 安装参考官方文档：https://mmcv.readthedocs.io/en/latest/get_started/installation.html
# wget -c https://download.openmmlab.com/mmcv/dist/cu113/torch1.10.0/mmcv_full-1.4.6-cp37-cp37m-manylinux1_x86_64.whl # This should change according to cuda version and pytorch version
# pip3 install --user mmcv_full-1.4.6-cp37-cp37m-manylinux1_x86_64.whl
pip install mmcv-full==1.4.6 -f https://download.openmmlab.com/mmcv/dist/cu113/torch1.10.0/index.html
pip3 install --user mmdet
git clone https://github.com/bdd100k/bdd100k.git
cd bdd100k
python3 setup.py develop --user  # 注意如果是安装到扩展包的话，都是使用 develop，install会出问题！
pip3 uninstall -y scalabel
pip3 install --user git+https://github.com/scalabel/scalabel.git
cd ../../..
```

# ERROR 记录

`pip install git+https` 始终不成功时，将下载链接改为 `git+http`.
如果还是不成功，将 `requirements.txt` 中的 `git+http` 包手动安装后，然后再将 `requirements.txt` 中的对应的内容注释，重新执行 `pip install -r requirements.txt`.

而且会首先下载 `git+https` 的包！如果不成功，`requirements.txt` 其余所有的包都不会被下载！！！

容易安装失败的单独安装！否则导致所有的包都没有安装上，非常浪费时间！！！

> [修改 setup.py 的源\_weixin_33853827 的博客-CSDN 博客](https://blog.csdn.net/weixin_33853827/article/details/85745938)

修改文件 `~/.pydistutils.cfg` 为：

```yaml
[easy_install]
index_url = https://pypi.tuna.tsinghua.edu.cn/simple
```

方法二：
直接在 `setup.py` 的同目录放置一个 `setup.cfg`,

```yaml
[easy_install]
index_url = https://pypi.tuna.tsinghua.edu.cn/simple
```

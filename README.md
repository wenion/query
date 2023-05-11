## Conda command
conda env create -f environment.yml
conda env list
conda activate myenv

conda info

### Updating an environment

### myclone - new environment/myenv existing environment
conda create --name myclone --clone myenv

conda list -n myenv

conda env remove --name myenv

### Installing packages
conda install --name myenv scipy
conda install scipy=0.15.0
conda install scipy curl

## project structure
NCI_model
|- main.py
|- infer.py
|- tabapp
   |- requirements.in
   |- development.ini
   |- setup.py
   |- tutorial
      |- __init__.py
      |- templates
         |- mytemplate.jinja2

## install requirements
python3 -m pip install -r requirements/requirements.txt

### runing console screen
screen -S xxx 是创建窗口
screen -ls 看现在有的窗口
screen -r xxx是打开已有的窗口
如果说那个被开启了 可以用screen -r -d xxx

## Conda command (Deprecated)
conda env create -f environment.yml
conda env list
conda activate myenv

conda info

### Updating an environment (Deprecated)

conda create --name myclone --clone myenv
* myclone - new environment
* myenv - existing environment

conda list -n myenv

conda env remove --name myenv

### Installing packages (Deprecated)
conda install --name myenv scipy
conda install scipy=0.15.0
conda install scipy curl

## project structure (Deprecated)
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

## Building the Docker Image
docker build -t query:v2.0.0 .

## Installing Requirements
export PYTHONPATH="/var/lib/hypothesis:$PYTHONPATH"
export TMPDIR=/app/tmp

## Running the Docker Container
docker run -d --network=dbs -v /app/query/data:/var/lib/hypothesis/data --env-file env.localhost.list -p 5005:5005 --name query query:v2.0.0

### For Testing (In Docker Container)
docker run -d --network=dbs -v /home/user/query/data:/var/lib/hypothesis/data -p 5005:5005 --name query query:v2.0.0

gunicorn --paste conf/query.ini --config conf/gunicorn-query.conf.py

### runing console screen
screen -S xxx 是创建窗口
screen -ls 看现在有的窗口
screen -r xxx是打开已有的窗口
如果说那个被开启了 可以用screen -r -d xxx

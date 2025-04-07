FROM pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime

RUN groupadd --system hypothesis && useradd --system --gid hypothesis --home-dir /var/lib/hypothesis --create-home hypothesis
WORKDIR /var/lib/hypothesis

COPY requirements.txt ./

# RUN apt-get update && apt-get install -y vim

RUN pip install --no-cache-dir -U pip \
    && pip install --no-cache-dir -r requirements.txt

# RUN apt-get remove --purge -y \
#     build-essential \
#     && apt-get autoremove -y && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY . .

EXPOSE 5005

ENV PATH /var/lib/hypothesis/bin:$PATH
ENV PYTHONIOENCODING utf_8
ENV PYTHONPATH /var/lib/hypothesis:$PYTHONPATH

USER hypothesis

# CMD ["sleep", "1000000"]
CMD ["gunicorn", "--paste", "conf/query.ini", "--config", "conf/gunicorn-query.conf.py"]

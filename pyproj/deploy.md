How to deploy new version
=========================

ssh into the host:
  ssh kayo@192.168.1.120
  ssh mjd@portal.superhouse.tv

```
cd register/pyproj
. env/bin/activate
git pull
pip install -r requirements.txt
# Check for changes to conf/.env.template and conf/local_settings.py_template
./manage.py migrate
pytest
./manage.py collectstatic --noinput
./manage.py check
sudo /usr/bin/systemctl stop gunicorn.service
```

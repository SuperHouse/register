How to deploy new version
=========================

```
ssh mjd@portal.superhouse.tv
cd ~/register-test/pyproj
. env/bin/activate
git pull
pip install -r requirements.txt
# Check for changes to conf/.env.template and conf/local_settings.py_template
./manage.py migrate
pytest
./manage.py collectstatic --noinput
./manage.py check
sudo /usr/bin/systemctl stop gunicorn-test.service
https://portaltest.superhouse.tv/device/
curl --request GET --url https://portaltest.superhouse.tv/api/v1/test-endpoint-noauth/ --header 'Content-Type: application/json' -w ' %{http_code}\n'
git status
git diff
deactivate
```

```
ssh mjd@portal.superhouse.tv
cd ~/register/pyproj
. env/bin/activate
git pull
pip install -r requirements.txt
# Check for changes to conf/.env.template and conf/local_settings.py_template
./manage.py migrate
pytest
./manage.py collectstatic --noinput
./manage.py check
sudo /usr/bin/systemctl stop gunicorn.service
https://portal.superhouse.tv/device/
curl --request GET --url https://portal.superhouse.tv/api/v1/test-endpoint-noauth/ --header 'Content-Type: application/json' -w ' %{http_code}\n'
git status
git diff
deactivate
```

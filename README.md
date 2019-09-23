dm2nsc
======

Data conversion tool for uploading Diabetes-M log data to Nightscout.

Install
------------------
docker build . -t dm2nsc

docker run --rm -it dn2nsc # run manual sync


-----------
Create cron to execute sync

add below lines to crontab using command crontab -e command

*/5 * * * * cd [path/to/your/dm2nsc] && [absolute/path/to/your/docker]docker run --rm -it dm2nsc | tee [path/to/logs]prod.log

*/30 * * * * cd  [path/to/your/dm2nsc]  && [absolute/path/to/your/docker]docker run --rm -it dm2nsc git pull | tee [path/to/logs]prod.log
------------------------------------------



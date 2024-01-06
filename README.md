# ExtronDatabaseConnector
Allows Extron processors to connect with an external database

Not affiliated with the Extron corporation

https://github.com/mefranklin6/ExtronDatabaseConnector

## Architecture
- Extron control processors send REST-like JSON API calls to a proxy web server, called FastAPI_Server.
- FastAPI server converts GET or POST commands from the processors into SQL SELECT/INSERT commands
- FastAPI server communicates with the database server, and sends data back to the control processors after converting back to JSON HTTP.

## Notes:
- The FastAPI server was built to be mostly asynchronous for best performance.  Sometimes commands will be processed out of order.
- The REST_Connector code on the control processors uses the Wait decorator as a multi-threaded hack to prevent blocking the main thread when waiting for the external servers.
- SQL Queries are never formatted on the control processors, we do not trust what the control processors say.  We handle SQL injection prevention and command formatting in the FastAPI app.
- The below is example instructions of how to setup a usage tracking metrics system, but the code can be modified to to any read/write to the database from Extron control processors.


# Prerequisites
## Server:
Requirements: 
- An x86 server running MySQL database (could be ported to other DB's too).  Instructions are for hosting on Ubuntu.
- An x86 server running modern Python 3 (built on 3.12.0). For this repo, this is the same server as the one running the database, but it can be two different servers.
- Reserved or Static IP's on servers
- An x86 management PC with Control Script Deployment Utility, basically your regular workstation.


## Extron Control Processors:
- Processors must be running Extron Control Script
- Deployment must be done by an Extron Authorized Programmer (So you can use Control Script Deployment Utility)


## Firewall Rules (if not on the same VLAN):
- TCP 22 SSH : From your management PC (if running headless servers)
- TCP 8080 HTTP : To/From FastAPI server and Extron processors
- TCP 3306 MySQL : To/From Database Server and FastAPI server (if running on different machines)
- TCP 3306 MySQL : To/From your management PC to access the database

# Instructions
## Install MySQL on Database Server:
- `sudo apt install mysql-server`

If using two servers: Bind the current IP of the server to the database
- `sudo nano /etc/mysql/mysql.conf.d/mysqld.cnf`
- Find 'bind-address' and set that to the IP of your server
- Write-out and exit nano

Enter MySQL as root
- `sudo mysql -u root`

Create a database: example, a database called 'devdb'
- `CREATE DATABASE devdb;`

Enter the database:
- `use devdb;`

Create a table: example, table named 'testextron'
- `CREATE TABLE testextron (`
- `room varchar(255),`
- `time varchar(255),`
- `metric varchar(255),`
- `action varchar(255)`
- `);`

## Create service account on MySQL that the FastAPI app will use:
Example: user named 'fast_api' with the password 'mypw', which will have INSERT (new write) and SELECT (read) privileges on the table 'testextron' in the database 'devdb'.  Only grant the minimum amount of privileges needed.  
Also, please use a better password or consider a better system of authentication.  The server IP should be the same as the bind address in `mysqld.cnf` that you set previously (it will be 127.0.0.1 if you didn't change it)
- `CREATE USER 'fast_api'@'<your server IP>' IDENTIFIED BY 'mypw';`
- `GRANT INSERT, SELECT ON devdb.testextron TO 'fast_api'@'<your server IP>';`
- `FLUSH PRIVILEGES;`

Open local firewall port from your FastAPI server and from your management station:
- `sudo ufw allow from <your FastAPI server IP> to any port 3306`
- `sudo ufw allow from <your workstation ip> to any port 3306`

## Recommended: Run the FastAPI App in a Python Virtual Enviroment
Copy this repo in to /opt/yourproject and cd into it
- `cd /opt/yourproject`

If needed, edit the `FastAPI_Server.py` with the proper credentials for your MySQL account you setup above.

- - If permissions error:
- - - `sudo chgrp -R user /opt/yourproject`
- - -  `sudo chmod -R g+rwx /opt/yourproject`

Install venv if you don't have it
- `sudo apt install python3.10-venv`

Create a virtual python enviroment called 'my-virt'
- `sudo python3 -m venv my-virt`

Start and enter the virtual enviroment
- `source /opt/yourproject/my-virt/bin/activate`
(replace 'source' with '.' if you have an error)

Install packages
- `pip install -r requirements.txt`
-  If permissions error:
- - `sudo chown -R $USER:$USER /opt/yourproject/my-virt/`

Exit the virtual enviroment:
- `deactivate`

Make a shell script that runs at boot which enters the virtual enviroment and starts the FastAPI app.
- `sudo nano /opt/yourproject/fastapi_startup.sh`

        cd /opt/yourproject
        source /opt/yourproject/my-virt/bin/activate
        python3 FastAPI_Server.py my-virt

Make the shell script and FastAPI app executable
- `sudo chmod +x fastapi_startup.sh`
- `sudo chmod +x FastAPI_Server.py`

Add the shell script to a 'on reboot' cron job:
- `crontab -e`
- (Add this at the top)
- - `@reboot /bin/bash -c /opt/yourproject/fastapi_startup.sh`
- Write out and exit


Reboot the server or just `./fastapi_startup.sh`.  

If you need to stop the App to make changes:
- Find the PID with `ps aux | grep ./FastAPI_Server.py`
- `kill -9 <the PID you found above>`

## Add the connector to your Control Processors
- Copy `REST_Connector.py` to your control processor repository.  I copied it to `/src/modules/project`

- Instantiate the connector in your control script code
    
        from modules.project.REST_Connector import REST_Connector
        API = REST_Connector(
            <str: this processor name>, 
            <str: IP address of your server>
        )



## Check Database Connection upon Startup
This will check the health of the app and database before sending additional commands. 

Recommended this is checked at every system startup.

In Extron Control Script:

    def Startup(): # your startup function
        @Wait(0.1) # multi-thread hack to prevent blocking
        def CheckMetricsEnabled():
            API.EnableAPI_Metrics = API.get_global_api_metrics_enable()
            print("API Metrics is {}".format(API.EnableAPI_Metrics))

## Example: POST a 'system on' metric:
Usage: call API.start_metric or API.stop_metric and pass the name of the metric as the only parameter
- At some system-on function, add: 

        API.start_metric("System On")
- This will end up in your database as:
-  - `|<processor name>|<current time in ISO format>|System On|Started` 

The paramater passed to API.start_metric can be any string under 255 characters.  This string is sanitized before being sent to the database to prevent SQL Injection.



## Example: Processor Read from a Table:
In FastAPI_Server.py, define an action and a page that acts as a trigger

In this example, we will read everything from a table called 'testtable' and send that to the processor when "Btn_GetTable" is pressed
        
        @app.get("/get_table")
        async def get_table():
            data = await db_connect.db_read('SELECT * FROM testtable')
            return {"message": data}

In Extron Control Script:

    @event(Btn_GetTable, "Pressed")
    def GetTable(btn, state):
        @Wait(0.1) # multi-thread hack to prevent blocking
        def GetTable_Inner():
            return API.rest_read(
                    url="<your_server_ip>:8080/get_table",
                    timeout=5 # remember this is non-blocking
            )

## Example: Handle Mutually Exclusive Metrics (like projector input)
In Extron Control Script:

    @event(Btn_PC_Input, "Pressed"):
    def SetInput_PC(btn, state):
        <switcher commands, GUI commands, etc>
        API.start_metric("PC", group="Inputs")

The current input is stored in the REST_Connector class.  When group is passed as a paramater and that group is "Inputs", it will unload and send a metrics stopped message of the old input and send a metrics started message for the new input.

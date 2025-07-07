Docker Management


GET
/is-docker-running
Is Docker Running



GET
/available-images/{image_name}
Available Images



GET
/active-containers
Active Containers



GET
/exited-containers
Exited Containers



POST
/clean-exited-containers
Clean Exited Containers



POST
/remove-container/{container_name}
Remove Container



POST
/stop-container/{container_name}
Stop Container



POST
/start-container/{container_name}
Start Container



POST
/create-hummingbot-instance
Create Hummingbot Instance



POST
/pull-image/
Pull Image


Manage Broker Messages


GET
/get-active-bots-status
Get Active Bots Status



GET
/get-bot-status/{bot_name}
Get Bot Status



GET
/get-bot-history/{bot_name}
Get Bot History



POST
/start-bot
Start Bot



POST
/stop-bot
Stop Bot



POST
/import-strategy
Import Strategy


Files Management


GET
/list-scripts
List Scripts



GET
/list-scripts-configs
List Scripts Configs



GET
/script-config/{script_name}
Get Script Config



GET
/list-controllers
List Controllers



GET
/controller-config-pydantic/{controller_type}/{controller_name}
Get Controller Config Pydantic



GET
/list-controllers-configs
List Controllers Configs



GET
/controller-config/{controller_name}
Get Controller Config



GET
/all-controller-configs
Get All Controller Configs



GET
/all-controller-configs/bot/{bot_name}
Get All Controller Configs For Bot



POST
/update-controller-config/bot/{bot_name}/{controller_id}
Update Controller Config



POST
/add-script
Add Script



POST
/upload-script
Upload Script



POST
/add-script-config
Add Script Config



POST
/upload-script-config
Upload Script Config



POST
/add-controller-config
Add Controller Config



POST
/upload-controller-config
Upload Controller Config



POST
/delete-controller-config
Delete Controller Config



POST
/delete-script-config
Delete Script Config



POST
/delete-all-controller-configs
Delete All Controller Configs



POST
/delete-all-script-configs
Delete All Script Configs


Market Data


POST
/real-time-candles
Get Candles



POST
/historical-candles
Get Historical Candles


Market Backtesting


POST
/run-backtesting
Run Backtesting


Database Management


POST
/list-databases
List Databases



POST
/read-databases
Read Databases



POST
/create-checkpoint
Create Checkpoint



POST
/list-checkpoints
List Checkpoints



POST
/load-checkpoint
Load Checkpoint


Market Performance


POST
/get-performance-results
Get Performance Results


Manage Credentials


GET
/accounts-state
Get All Accounts State



GET
/account-state-history
Get Account State History



GET
/available-connectors
Available Connectors



GET
/connector-config-map/{connector_name}
Get Connector Config Map



GET
/all-connectors-config-map
Get All Connectors Config Map



GET
/list-accounts
List Accounts



GET
/list-credentials/{account_name}
List Credentials



POST
/add-account
Add Account



POST
/delete-account
Delete Account



POST
/delete-credential/{account_name}/{connector_name}
Delete Credential



POST
/add-connector-keys/{account_name}/{connector_name}
Add Connector Keys



Schemas
BacktestingConfigExpand allobject
Body_upload_controller_config_upload_controller_config_postExpand allobject
Body_upload_script_config_upload_script_config_postExpand allobject
Body_upload_script_upload_script_postExpand allobject
CandlesConfigExpand allobject
HTTPValidationErrorExpand allobject
HistoricalCandlesConfigExpand allobject
HummingbotInstanceConfigExpand allobject
ImageNameExpand allobject
ImportStrategyActionExpand allobject
ScriptExpand allobject
ScriptConfigExpand allobject
StartBotActionExpand allobject
StopBotActionExpand allobject
ValidationErrorExpand allobject

### Developer Utility (used by scaffold)

The CLI scaffolding helper relies on two existing endpoints:

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/list-controllers` | Returns a JSON mapping `{controller_type: ["file.py", …]}`. |
| GET | `/controller-config-pydantic/{controller_type}/{controller_file}` | Returns the default Pydantic config of that controller as JSON. |

Both routes are protected by basic-auth (`admin:admin` in dev) and require the backend to be running.
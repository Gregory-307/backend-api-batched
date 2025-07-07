import json
from typing import Dict, List, get_args, get_origin, Any

import yaml
from fastapi import APIRouter, File, HTTPException, UploadFile
from starlette import status

from models import Script, ScriptConfig
from utils.file_system import FileSystemUtil
from inspect import isclass
from pydantic import BaseModel
from pydantic.fields import PydanticUndefined
from enum import Enum

router = APIRouter(tags=["Files Management"])

file_system = FileSystemUtil()


def _placeholder_for_annotation(ann: Any):
    """Return a generic placeholder based on type annotation."""
    origin = get_origin(ann)
    if origin is list:
        return []
    if origin is dict:
        return {}
    if ann in {int, float}:
        return 0
    if ann is str:
        return ""
    return None


def _convert_comma_sep(value: str, subtype: Any):
    """Convert a comma-separated string to list[ subtype ]."""
    parts = [p.strip() for p in value.split(",") if p.strip()]
    if subtype in (int, float):
        def cast(x):
            try:
                return subtype(x)
            except Exception:
                return x
        return [cast(p) for p in parts]
    return parts


def build_defaults(model_cls: type[BaseModel]) -> Dict[str, Any]:
    """Return a fully-populated default dict for *model_cls*, recursively."""
    instance = model_cls.model_construct()  # skips validation, fills defaults
    # Using JSON mode ensures Enum members serialize to their underlying value (int/str) rather
    # than the less useful "EnumClass.VALUE" string representation.
    data: Dict[str, Any] = instance.model_dump(mode="json", exclude_unset=False)

    for name, field in model_cls.model_fields.items():
        ann = field.annotation
        origin = get_origin(ann)
        subtype = get_args(ann)[0] if origin is list and get_args(ann) else Any
        val = data.get(name, PydanticUndefined)

        # Handle list conversions ------------------------------------------------
        if origin is list:
            # Avoid converting when the subtype is itself a list (e.g. List[List[Decimal]]).
            nested_list = get_origin(subtype) is list
            if isinstance(val, str) and not nested_list:  # comma-separated defaults
                data[name] = _convert_comma_sep(val, subtype)
            elif val is None:
                data[name] = []
            elif isclass(subtype) and issubclass(subtype, BaseModel):
                # leave empty list; creating sample nested objects often breaks validation
                data[name] = []
            continue

        # Handle nested Pydantic model ------------------------------------------
        if isclass(ann) and issubclass(ann, BaseModel):
            if val is None or val == {}:
                data[name] = build_defaults(ann)
            continue

        # Replace PydanticUndefined / None with placeholder ----------------------
        if val is PydanticUndefined or val is None:
            data[name] = _placeholder_for_annotation(ann)

    # Ensure mandatory identifier fields are present
    for key in ("controller_name", "controller_type"):
        if not data.get(key):
            attr_val = getattr(model_cls, key, None)
            if isinstance(attr_val, str) and attr_val:
                data[key] = attr_val

    # --- Post-processing fixes ----------------------------------------------
    def _serialise_enums(obj):
        """Recursively convert Enum objects to their .value primitive."""
        if isinstance(obj, Enum):
            return obj.value
        if isinstance(obj, list):
            return [_serialise_enums(x) for x in obj]
        if isinstance(obj, dict):
            return {k: _serialise_enums(v) for k, v in obj.items()}
        return obj

    data = _serialise_enums(data)

    # Prefer sandbox exchange for scaffolds to avoid live REST calls.
    conn = data.get("connector_name")
    if isinstance(conn, str) and conn.lower().startswith("binance"):
        data["connector_name"] = "kucoin"

    # ------------------------------------------------------------------
    # Derive missing connector / trading_pair for multi-exchange controllers
    # ------------------------------------------------------------------
    if "connector_name" in model_cls.model_fields and not data.get("connector_name"):
        ep1 = data.get("exchange_pair_1")
        if isinstance(ep1, dict) and ep1.get("connector_name"):
            data["connector_name"] = ep1["connector_name"]

    if "trading_pair" in model_cls.model_fields and not data.get("trading_pair"):
        ep1 = data.get("exchange_pair_1")
        if isinstance(ep1, dict) and ep1.get("trading_pair"):
            data["trading_pair"] = ep1["trading_pair"]
        else:
            quote = data.get("quote_asset") or "USDT"
            portfolio = data.get("portfolio_allocation")
            if isinstance(portfolio, dict) and portfolio:
                first_asset = next(iter(portfolio))
                data["trading_pair"] = f"{first_asset}-{quote}"

    # ------------------------------------------------------------------
    # Provide a sensible candles_config if missing (avoids timestamp_bt errors)
    # ------------------------------------------------------------------
    if (data.get("candles_config") in (None, [])) and data.get("connector_name") and data.get("trading_pair"):
        data["candles_config"] = [{
            "connector": data["connector_name"],
            "trading_pair": data["trading_pair"],
            "interval": "3m",
        }]

    # Kucoin doesn't list FDUSD pairs – swap to USDT for placeholders
    def _sanitise_pair(pair: str) -> str:
        if not isinstance(pair, str) or "-" not in pair:
            return pair
        base, quote = pair.split("-", 1)
        if base in {"WLD", "PEPE"}:
            base = "BTC"
        if quote == "FDUSD":
            quote = "USDT"
        return f"{base}-{quote}"

    if data.get("connector_name") == "kucoin" and isinstance(data.get("trading_pair"), str):
        data["trading_pair"] = _sanitise_pair(data["trading_pair"])

    # Propagate same sanitisation to candles_config and candles_trading_pair
    if isinstance(data.get("candles_trading_pair"), str):
        data["candles_trading_pair"] = _sanitise_pair(data["candles_trading_pair"])

    if isinstance(data.get("candles_config"), list):
        for feed in data["candles_config"]:
            if isinstance(feed, dict) and "trading_pair" in feed:
                feed["trading_pair"] = _sanitise_pair(feed["trading_pair"])

    # Fill optional explicit candles_connector / candles_trading_pair so controllers like
    # dman_v3 that reference them don't break when scaffolds omit them.
    if "candles_connector" in model_cls.model_fields and not data.get("candles_connector"):
        data["candles_connector"] = data.get("connector_name")

    if "candles_trading_pair" in model_cls.model_fields and not data.get("candles_trading_pair"):
        data["candles_trading_pair"] = data.get("trading_pair")

    return data


@router.get("/list-scripts", response_model=List[str])
async def list_scripts():
    return file_system.list_files('scripts')


@router.get("/list-scripts-configs", response_model=List[str])
async def list_scripts_configs():
    return file_system.list_files('conf/scripts')


@router.get("/script-config/{script_name}", response_model=dict)
async def get_script_config(script_name: str):
    """
    Retrieves the configuration parameters for a given script.
    :param script_name: The name of the script.
    :return: JSON containing the configuration parameters.
    """
    config_class = file_system.load_script_config_class(script_name)
    if config_class is None:
        raise HTTPException(status_code=404, detail="Script configuration class not found")

    # Extracting fields and default values using the improved logic
    config_fields = build_defaults(config_class)
    return json.loads(json.dumps(config_fields, default=str))


@router.get("/list-controllers", response_model=dict)
async def list_controllers():
    directional_trading_controllers = [file for file in file_system.list_files('controllers/directional_trading') if
                                       file != "__init__.py"]
    market_making_controllers = [file for file in file_system.list_files('controllers/market_making') if
                                 file != "__init__.py"]
    generic_controllers = [file for file in file_system.list_files('controllers/generic') if file != "__init__.py"]

    return {"directional_trading": directional_trading_controllers,
            "market_making": market_making_controllers,
            "generic": generic_controllers}

@router.get("/controller-config-pydantic/{controller_type}/{controller_name}", response_model=dict)
async def get_controller_config_pydantic(controller_type: str, controller_name: str):
    """
    Retrieves the configuration parameters for a given controller.
    :param controller_name: The name of the controller.
    :return: JSON containing the configuration parameters.
    """
    config_class = file_system.load_controller_config_class(controller_type, controller_name)
    if config_class is None:
        raise HTTPException(status_code=404, detail="Controller configuration class not found")

    # Extracting fields and default values using the improved logic
    config_fields = build_defaults(config_class)
    return json.loads(json.dumps(config_fields, default=str))


@router.get("/list-controllers-configs", response_model=List[str])
async def list_controllers_configs():
    return file_system.list_files('conf/controllers')


@router.get("/controller-config/{controller_name}", response_model=dict)
async def get_controller_config(controller_name: str):
    config = file_system.read_yaml_file(f"bots/conf/controllers/{controller_name}.yml")
    return config


@router.get("/all-controller-configs", response_model=List[dict])
async def get_all_controller_configs():
    configs = []
    for controller in file_system.list_files('conf/controllers'):
        config = file_system.read_yaml_file(f"bots/conf/controllers/{controller}")
        configs.append(config)
    return configs


@router.get("/all-controller-configs/bot/{bot_name}", response_model=List[dict])
async def get_all_controller_configs_for_bot(bot_name: str):
    configs = []
    bots_config_path = f"instances/{bot_name}/conf/controllers"
    if not file_system.path_exists(bots_config_path):
        raise HTTPException(status_code=400, detail="Bot not found.")
    for controller in file_system.list_files(bots_config_path):
        config = file_system.read_yaml_file(f"bots/{bots_config_path}/{controller}")
        configs.append(config)
    return configs


@router.post("/update-controller-config/bot/{bot_name}/{controller_id}")
async def update_controller_config(bot_name: str, controller_id: str, config: Dict):
    bots_config_path = f"instances/{bot_name}/conf/controllers"
    if not file_system.path_exists(bots_config_path):
        raise HTTPException(status_code=400, detail="Bot not found.")
    current_config = file_system.read_yaml_file(f"bots/{bots_config_path}/{controller_id}.yml")
    current_config.update(config)
    file_system.dump_dict_to_yaml(f"bots/{bots_config_path}/{controller_id}.yml", current_config)
    return {"message": "Controller configuration updated successfully."}


@router.post("/add-script", status_code=status.HTTP_201_CREATED)
async def add_script(script: Script, override: bool = False):
    try:
        file_system.add_file('scripts', script.name + '.py', script.content, override)
        return {"message": "Script added successfully."}
    except FileExistsError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/upload-script")
async def upload_script(config_file: UploadFile = File(...), override: bool = False):
    try:
        contents = await config_file.read()
        file_system.add_file('scripts', config_file.filename, contents.decode(), override)
        return {"message": "Script uploaded successfully."}
    except FileExistsError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/add-script-config", status_code=status.HTTP_201_CREATED)
async def add_script_config(config: ScriptConfig):
    try:
        yaml_content = yaml.dump(config.content)

        file_system.add_file('conf/scripts', config.name + '.yml', yaml_content, override=True)
        return {"message": "Script configuration uploaded successfully."}
    except Exception as e:  # Consider more specific exception handling
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/upload-script-config")
async def upload_script_config(config_file: UploadFile = File(...), override: bool = False):
    try:
        contents = await config_file.read()
        file_system.add_file('conf/scripts', config_file.filename, contents.decode(), override)
        return {"message": "Script configuration uploaded successfully."}
    except FileExistsError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/add-controller-config", status_code=status.HTTP_201_CREATED)
async def add_controller_config(config: ScriptConfig):
    try:
        yaml_content = yaml.dump(config.content)

        file_system.add_file('conf/controllers', config.name + '.yml', yaml_content, override=True)
        return {"message": "Controller configuration uploaded successfully."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/upload-controller-config")
async def upload_controller_config(config_file: UploadFile = File(...), override: bool = False):
    try:
        contents = await config_file.read()
        file_system.add_file('conf/controllers', config_file.filename, contents.decode(), override)
        return {"message": "Controller configuration uploaded successfully."}
    except FileExistsError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/delete-controller-config", status_code=status.HTTP_200_OK)
async def delete_controller_config(config_name: str):
    try:
        file_system.delete_file('conf/controllers', config_name)
        return {"message": f"Controller configuration {config_name} deleted successfully."}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/delete-script-config", status_code=status.HTTP_200_OK)
async def delete_script_config(config_name: str):
    try:
        file_system.delete_file('conf/scripts', config_name)
        return {"message": f"Script configuration {config_name} deleted successfully."}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/delete-all-controller-configs", status_code=status.HTTP_200_OK)
async def delete_all_controller_configs():
    try:
        for file in file_system.list_files('conf/controllers'):
            file_system.delete_file('conf/controllers', file)
        return {"message": "All controller configurations deleted successfully."}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/delete-all-script-configs", status_code=status.HTTP_200_OK)
async def delete_all_script_configs():
    try:
        for file in file_system.list_files('conf/scripts'):
            file_system.delete_file('conf/scripts', file)
        return {"message": "All script configurations deleted successfully."}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

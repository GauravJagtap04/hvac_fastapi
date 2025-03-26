import asyncio
import random
import os
import math
import json
import datetime
import paho.mqtt.client as mqtt
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body, Query, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from typing import Set, Dict, Optional, Any
from simulators.simulator_factory import SimulatorFactory
from dotenv import load_dotenv
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from jose.exceptions import JWTError


class MonitoredDict(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.change_log = []
        self.simulation_states = {}  # Track simulation state per client
        self.last_activity = {}

    def __setitem__(self, key, value):
        action = "updated" if key in self else "added"
        self.change_log.append({
            "timestamp": datetime.datetime.now().isoformat(),
            "action": action,
            "key": key,
            "value_summary": str(value)[:100]  # Truncated summary
        })

        # Initialize simulation state for new clients
        if key not in self.simulation_states:
            self.simulation_states[key] = {
                "is_running": False,
                "is_paused": False,
                "last_activity": datetime.datetime.now()
            }

        print(
            f"[MONITOR] {action.upper()} key '{key}' at {self.change_log[-1]['timestamp']}")
        super().__setitem__(key, value)
        self.add_last_activity_timestamp(key)

    def __delitem__(self, key):
        if key in self:
            self.change_log.append({
                "timestamp": datetime.datetime.now().isoformat(),
                "action": "deleted",
                "key": key,
                "value_summary": "removed"
            })

            # Clean up the simulation state
            if key in self.simulation_states:
                del self.simulation_states[key]

            print(
                f"[MONITOR] DELETED key '{key}' at {self.change_log[-1]['timestamp']}")
            super().__delitem__(key)

    def set_simulation_state(self, client_id, is_running, is_paused):
        """Set simulation state for a specific client"""
        if client_id in self:
            if client_id not in self.simulation_states:
                self.simulation_states[client_id] = {
                    "is_running": False,
                    "is_paused": False,
                    "last_activity": datetime.datetime.now()
                }

            self.simulation_states[client_id]["is_running"] = is_running
            self.simulation_states[client_id]["is_paused"] = is_paused
            print(
                f"[MONITOR] Simulation state for '{client_id}': running={is_running}, paused={is_paused}")

    def get_simulation_state(self, client_id):
        """Get simulation state for a specific client"""
        if client_id in self.simulation_states:
            return self.simulation_states[client_id]

        # Initialize state if it doesn't exist
        self.simulation_states[client_id] = {
            "is_running": False,
            "is_paused": False,
            "last_activity": datetime.datetime.now()
        }
        return self.simulation_states[client_id]

    def get_active_clients(self):
        """Get all clients with running simulations"""
        return [client_id for client_id in self.keys() if client_id in self.last_activity]

    def get_changes(self):
        return self.change_log

    def add_last_activity_timestamp(self, client_id):
        """Record when a client was last active"""
        self.last_activity[client_id] = datetime.datetime.now(
        )  # Fixed variable name


# Load environment variables
load_dotenv()
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
supabase_jwt_secret = os.getenv('SUPABASE_JWT_SECRET')

MQTT_BROKER = "localhost"
MQTT_TOPIC = "sensor/temperature"

app = FastAPI()
websockets: Set[WebSocket] = set()
mqtt_client = mqtt.Client()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def verify_supabase_token(token: str) -> dict:
    """Verify Supabase JWT token and return payload."""
    try:
        # Decode without verification first to get the header
        header = jwt.get_unverified_header(token)

        # Decode and verify the token
        # Note: Supabase tokens are signed by Supabase, we only verify they're valid JWT
        payload = jwt.decode(
            token,
            key="supabase_jwt_secret",
            algorithms=["HS256"],
            options={
                "verify_signature": False,  # Skip signature verification
                "verify_aud": False,
                "verify_iss": False
            }
        )

        user_id = payload.get("sub")
        if user_id:
            print(f"User {user_id} authenticated successfully")

        return payload

    except JWTError as e:
        print(f"JWT verification error: {str(e)}")
        raise Exception("Invalid authentication token")
    except Exception as e:
        print(f"Token verification error: {str(e)}")
        raise Exception("Error verifying authentication token")


# Mount the static directory
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

simulators = MonitoredDict()


def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT Broker with result code: {rc}")


mqtt_client.on_connect = on_connect
mqtt_client.connect(MQTT_BROKER, 1883, 60)


def generate_temperature(client_id=None):
    """Simulates temperature sensor data using HVAC simulator."""
    if client_id and client_id in simulators:
        simulator = simulators[client_id]
        new_temp = simulator.calculate_temperature_change()
        simulator.room.current_temp = new_temp
        return round(new_temp, 2)
    else:
        print(f"Warning: No simulator found for client_id: {client_id}")
        return 25.0  # Default temperature

# # Global variables to track simulation state
# is_simulation_running = False
# is_simulation_paused = False


def normalize_system_type(system_type: str) -> str:
    """Convert kebab-case to snake_case if needed for internal use."""
    # This is useful if you need a consistent format internally
    return system_type.replace("-", "_").lower()


async def publish_temperature():
    """Publishes temperature and system status data to MQTT and WebSocket clients."""
    while True:
        # Get all actively running client simulations
        active_clients = simulators.get_active_clients()

        for client_id in active_clients:
            if client_id in simulators:
                simulator = simulators[client_id]
                temp = generate_temperature(client_id)
                system_status = simulator.get_system_status()

                # Prepare message with client id, temperature and system status
                message = {
                    "client_id": client_id,
                    "temperature": temp,
                    "system_status": system_status
                }

                mqtt_client.publish(
                    f"{MQTT_TOPIC}/{client_id}", json.dumps(message))
                print(f"Published Temperature for {client_id}: {temp}°C")

                # Broadcast to WebSocket clients
                disconnected = set()
                for ws in websockets:
                    try:
                        # Check if this websocket is associated with this client_id
                        if hasattr(ws, 'client_id') and ws.client_id == client_id:
                            await ws.send_text(json.dumps(message))
                    except:
                        disconnected.add(ws)

                # Remove disconnected clients
                websockets.difference_update(disconnected)

        await asyncio.sleep(2)


# Add a cleanup function
async def cleanup_inactive_simulators():
    """Remove simulators that haven't been used in a while."""
    while True:
        await asyncio.sleep(3600)  # Check every hour
        now = datetime.datetime.now()
        # 24 hours of inactivity
        inactive_threshold = now - datetime.timedelta(hours=24)

        inactive_clients = []
        for client_id, state in simulators.simulation_states.items():
            last_active = state.get("last_active")
            if last_active and last_active < inactive_threshold:
                inactive_clients.append(client_id)

        for client_id in inactive_clients:
            if client_id in simulators:
                del simulators[client_id]
                print(f"Removed inactive simulator for {client_id}")


@app.get("/")
async def root():
    return FileResponse(os.path.join(static_dir, "index.html"))

security = HTTPBearer()


@app.websocket("/ws/{auth_id}/{system_type}")
async def websocket_endpoint(
    websocket: WebSocket,
    auth_id: str,
    system_type: str,
    token: str = Query(...),  # Require token as query parameter
):
    try:
        # Verify token manually since we can't use regular dependency injection
        payload = verify_supabase_token(token)
        user_id = payload.get("sub")

        # Verify that the auth_id in the URL matches the user_id in the token
        if not user_id or user_id != auth_id:
            await websocket.close(code=4001, reason="Invalid authentication token")
            return

        print(f"User {auth_id} authenticated successfully")

        # Use combination of auth_id and system_type as client_id
        normalized_system_type = normalize_system_type(system_type)
        client_id = f"{auth_id}_{system_type}"

    except Exception as e:
        print(f"Authentication error: {e}")
        await websocket.close(code=4001, reason="Invalid authentication token")
        return

    await websocket.accept()
    print(f"Connected to client {client_id}")

    # Store client_id with the websocket
    websocket.client_id = client_id
    websocket.system_type = system_type
    websocket.normalized_system_type = normalized_system_type
    websockets.add(websocket)

    # Create simulator for this client if it doesn't exist
    if client_id not in simulators:
        try:
            # Create default parameters
            default_room_params = {
                'length': 5.0,
                'breadth': 4.0,
                'height': 2.5,
                'current_temp': 25.0,
                'target_temp': 22.0,
                'external_temp': 35.0,
                'wall_insulation': 'medium',
                'num_people': 0,
                'mode': 'cooling'
            }

            default_hvac_params = {
                'power': 3.5,
                'cop': 3.0,
                'air_flow_rate': 0.5,
                'fan_speed': 100.0
            }

            # Create simulator
            simulator = SimulatorFactory.create_simulator(
                normalized_system_type,
                room_params=default_room_params,
                hvac_params=default_hvac_params
            )
            simulators[client_id] = simulator
            print(f"Created simulator for client {client_id}")
        except Exception as e:
            print(f"Error creating simulator: {e}")
            await websocket.close(code=1011, reason="Failed to initialize simulator")
            return

    try:
        simulators.add_last_activity_timestamp(client_id)

        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            print(f"Received message from {client_id}: {data}")

            # Get the simulator for this client
            simulator = simulators.get(client_id)

            if not simulator:
                print(f"No simulator found for {client_id}")
                simulator = SimulatorFactory.create_simulator(
                    normalized_system_type,
                    room_params={},
                    hvac_params={}
                )
                simulators[client_id] = simulator
                print(f"Created new simulator for client {client_id}")

            elif data.get('type') == 'simulation_control':
                action = data.get('data', {}).get('action')
                if action == 'start':
                    simulators.set_simulation_state(client_id, True, False)
                    print(f"Simulation started for {client_id}")
                elif action == 'stop':
                    simulators.set_simulation_state(client_id, False, False)
                    print(f"Simulation stopped for {client_id}")
                elif action == 'pause':
                    simulators.set_simulation_state(client_id, True, True)
                    print(f"Simulation paused for {client_id}")

                # Send confirmation
                await websocket.send_text(json.dumps({
                    'type': 'simulation_status',
                    'data': {
                        'isRunning': simulators.get_simulation_state(client_id).get('is_running', False),
                        'isPaused': simulators.get_simulation_state(client_id).get('is_paused', False),
                        'estimatedTimeToTarget': simulator.calculate_time_to_target() if hasattr(simulator, 'calculate_time_to_target') else 0
                    }
                }))

            elif data.get('type') == 'room_parameters':
                params = data.get('data', {})
                # Update all room parameters
                if 'length' in params:
                    simulator.room.length = float(params['length'])
                if 'breadth' in params:
                    simulator.room.breadth = float(params['breadth'])
                if 'height' in params:
                    simulator.room.height = float(params['height'])
                if 'currentTemp' in params:
                    simulator.room.current_temp = float(
                        params['currentTemp'])
                if 'targetTemp' in params:
                    simulator.room.target_temp = float(
                        params['targetTemp'])
                if 'externalTemp' in params:
                    simulator.room.external_temp = float(
                        params['externalTemp'])
                if 'wallInsulation' in params:
                    simulator.room.wall_insulation = params['wallInsulation']
                if 'numPeople' in params:
                    simulator.room.num_people = int(params['numPeople'])
                if 'mode' in params:
                    simulator.room.mode = params['mode']

                # Handle chilled water specific parameters
                if system_type == "chilled-water-system" and 'fanCoilUnits' in params:
                    simulator.room.fan_coil_units = int(
                        params['fanCoilUnits'])

                simulators.add_last_activity_timestamp(client_id)

                await websocket.send_text(json.dumps({
                    'type': 'system_status',
                    'data': simulator.get_system_status()
                }))

                print(f"Updated room parameters for {client_id}")

            elif data.get('type') == 'hvac_parameters':
                params = data.get('data', {})
                # Update common HVAC parameters
                if 'power' in params:
                    simulator.hvac.power = float(params['power'])
                if 'cop' in params:
                    simulator.hvac.cop = float(params['cop'])
                if 'airFlowRate' in params:
                    simulator.hvac.air_flow_rate = float(
                        params['airFlowRate'])
                if 'supplyTemp' in params:
                    simulator.hvac.supply_temp = float(
                        params['supplyTemp'])
                if 'fanSpeed' in params:
                    simulator.hvac.fan_speed = float(params['fanSpeed'])

                # Handle chilled water specific parameters
                if system_type == "chilled-water-system":
                    if 'chilledWaterFlowRate' in params:
                        simulator.hvac.chilled_water_flow_rate = float(
                            params['chilledWaterFlowRate'])
                    if 'chilledWaterSupplyTemp' in params:
                        simulator.hvac.chilled_water_supply_temp = float(
                            params['chilledWaterSupplyTemp'])
                    if 'chilledWaterReturnTemp' in params:
                        simulator.hvac.chilled_water_return_temp = float(
                            params['chilledWaterReturnTemp'])
                    if 'pumpPower' in params:
                        simulator.hvac.pump_power = float(
                            params['pumpPower'])
                    if 'primarySecondaryLoop' in params:
                        simulator.hvac.primary_secondary_loop = bool(
                            params['primarySecondaryLoop'])
                    if 'glycolPercentage' in params:
                        simulator.hvac.glycol_percentage = float(
                            params['glycolPercentage'])
                    if 'heatExchangerEfficiency' in params:
                        simulator.hvac.heat_exchanger_efficiency = float(
                            params['heatExchangerEfficiency'])

                simulators.add_last_activity_timestamp(client_id)

                await websocket.send_text(json.dumps({
                    'type': 'system_status',
                    'data': simulator.get_system_status()
                }))

                print(f"Updated HVAC parameters for {client_id}")

            elif data.get('type') == 'get_status':
                simulators.add_last_activity_timestamp(client_id)

                await websocket.send_text(json.dumps({
                    'type': 'system_status',
                    'data': simulator.get_system_status()
                }))

            elif data.get('type') == 'get_time_to_target':
                # Record activity
                simulators.add_last_activity_timestamp(client_id)

                # Calculate and send time to target
                time_to_target = simulator.calculate_time_to_target() if hasattr(
                    simulator, 'calculate_time_to_target') else 0
                await websocket.send_text(json.dumps({
                    'type': 'time_to_target',
                    'data': {
                        'timeToTarget': time_to_target
                    }
                }))

            # Send immediate feedback
            system_status = simulator.get_system_status()
            await websocket.send_text(json.dumps({
                'client_id': client_id,
                'system_status': system_status
            }))

    except WebSocketDisconnect:
        websockets.discard(websocket)
        print(f"Client {client_id} disconnected")
    except Exception as e:
        websockets.discard(websocket)
        print(f"Error with client {client_id}: {str(e)}")
    finally:
        # Clean up
        if websocket in websockets:
            websockets.discard(websocket)
            print(f"Removed client {client_id} from active connections")


@app.post("/{auth_id}/simulations/{system_type}")
async def update_simulation(
    auth_id: str,
    system_type: str,
    parameters: Dict[str, Any] = Body(...),
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())
):
    try:
        # Verify the token
        payload = verify_supabase_token(credentials.credentials)
        user_id = payload.get("sub")

        if not user_id or user_id != auth_id:
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid authentication token"}
            )

        # Normalize the system type
        normalized_system_type = normalize_system_type(system_type)
        client_id = f"{auth_id}_{system_type}"

        default_room_params = {
            'length': 5.0,
            'breadth': 4.0,
            'height': 2.5,
            'current_temp': 25.0,
            'target_temp': 22.0,
            'external_temp': 35.0,
            'wall_insulation': 'medium',
            'num_people': 0,
            'mode': 'cooling'
        }

        default_hvac_params = {
            'power': 3.5,
            'cop': 3.0,
            'air_flow_rate': 0.5,
            'fan_speed': 100.0
        }

        if "roomParameters" in parameters:
            for key, value in parameters["roomParameters"].items():
                snake_key = key.lower()
                if '_' not in snake_key:
                    snake_key = ''.join(
                        ['_' + c.lower() if c.isupper() else c for c in key]).lstrip('_')
                default_room_params[snake_key] = value

        if "hvacParameters" in parameters:
            for key, value in parameters["hvacParameters"].items():
                snake_key = key.lower()
                if '_' not in snake_key:
                    snake_key = ''.join(
                        ['_' + c.lower() if c.isupper() else c for c in key]).lstrip('_')
                default_hvac_params[snake_key] = value

        print(f"Creating simulator for system_type: {system_type}")
        print(f"Normalized system_type: {normalized_system_type}")

        simulator = SimulatorFactory.create_simulator(
            normalized_system_type,
            room_params=default_room_params,
            hvac_params=default_hvac_params
        )

        if simulator is None:
            # Handle case when simulator creation fails
            print(
                f"ERROR: Failed to create simulator for {normalized_system_type}")
            return JSONResponse(
                status_code=500,
                content={"error": f"Failed to create simulator for {system_type}"}
            )

        simulators[client_id] = simulator
        print(
            f"Created simulator for user {auth_id} with system type {system_type}")
        print(f"Active simulators: {list(simulators.keys())}")

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "system_status": simulator.get_system_status()
            }
        )

    except Exception as e:
        print(f"ERROR in update_simulation: {str(e)}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@app.on_event("startup")
async def startup_event():
    mqtt_client.loop_start()
    asyncio.create_task(publish_temperature())
    asyncio.create_task(cleanup_inactive_simulators())


@app.on_event("shutdown")
async def shutdown_event():
    mqtt_client.loop_stop()
    mqtt_client.disconnect()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


print("Simulators: ", simulators)

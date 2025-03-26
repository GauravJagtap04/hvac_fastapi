from typing import Dict, Any
from .split_system_simulator import SplitSystemSimulator, SplitRoomParameters, SplitHVACParameters
from .vrf_system_simulator import VRFSystemSimulator, VRFRoomParameters, VRFHVACParameters
from .heat_pump_system_simulator import HeatPumpSystemSimulator, HeatPumpRoomParameters, HeatPumpHVACParameters
from .chilled_water_system_simulator import ChilledWaterSystemSimulator, ChilledWaterRoomParameters, ChilledWaterHVACParameters


class SimulatorFactory:
    @staticmethod
    def create_simulator(system_type: str, room_params: Dict[str, Any], hvac_params: Dict[str, Any]):
        """Create and return the appropriate simulator based on system type"""
        system_type = system_type.replace("-", "_").replace(" ", "_").lower()

        if system_type == "split_system":
            room = SplitRoomParameters(
                length=float(room_params.get('length', 5.0)),
                breadth=float(room_params.get('breadth', 4.0)),
                height=float(room_params.get('height', 2.5)),
                current_temp=float(room_params.get('current_temp', 25.0)),
                target_temp=float(room_params.get('target_temp', 22.0)),
                external_temp=float(room_params.get('external_temp', 35.0)),
                wall_insulation=room_params.get('wall_insulation', 'medium'),
                num_people=int(room_params.get('num_people', 0)),
                mode=room_params.get('mode', 'cooling'),
                humidity=float(room_params.get('humidity', 50.0)),
                heat_gain_external=float(
                    room_params.get('heat_gain_external', 0.0))
            )

            hvac = SplitHVACParameters(
                power=float(hvac_params.get('power', 3.5)),
                cop=float(hvac_params.get('cop', 3.0)),
                air_flow_rate=float(hvac_params.get('air_flow_rate', 0.5)),
                supply_temp=float(hvac_params.get('supply_temp', 12.0)),
                fan_speed=float(hvac_params.get('fan_speed', 100.0)),
                time_interval=float(hvac_params.get('time_interval', 1.0))
            )

            return SplitSystemSimulator(room, hvac)

        elif system_type == "chilled_water_system":
            room = ChilledWaterRoomParameters(
                length=float(room_params.get('length', 5.0)),
                breadth=float(room_params.get('breadth', 4.0)),
                height=float(room_params.get('height', 2.5)),
                current_temp=float(room_params.get('current_temp', 25.0)),
                target_temp=float(room_params.get('target_temp', 22.0)),
                external_temp=float(room_params.get('external_temp', 35.0)),
                wall_insulation=room_params.get('wall_insulation', 'medium'),
                num_people=int(room_params.get('num_people', 0)),
                mode=room_params.get('mode', 'cooling'),
                humidity=float(room_params.get('humidity', 50.0)),
                heat_gain_external=float(
                    room_params.get('heat_gain_external', 0.0)),
                fan_coil_units=int(room_params.get('fan_coil_units', 1))
            )

            hvac = ChilledWaterHVACParameters(
                power=float(hvac_params.get('power', 3.5)),
                cop=float(hvac_params.get('cop', 3.0)),
                air_flow_rate=float(hvac_params.get('air_flow_rate', 0.5)),
                supply_temp=float(hvac_params.get('supply_temp', 12.0)),
                fan_speed=float(hvac_params.get('fan_speed', 100.0)),
                time_interval=float(hvac_params.get('time_interval', 1.0)),
                chilled_water_flow_rate=float(
                    hvac_params.get('waterFlowRate', 0.5)),
                chilled_water_supply_temp=float(
                    hvac_params.get('chilled_water_supply_temp', 7.0)),
                chilled_water_return_temp=float(
                    hvac_params.get('chilled_water_return_temp', 12.0)),
                pump_power=float(hvac_params.get('pump_power', 0.75)),
                primary_secondary_loop=bool(
                    hvac_params.get('primary_secondary_loop', True)),
                glycol_percentage=float(
                    hvac_params.get('glycol_percentage', 0)),
                heat_exchanger_efficiency=float(
                    hvac_params.get('heat_exchanger_efficiency', 0.85))
            )

            return ChilledWaterSystemSimulator(room, hvac)

        elif system_type == "heat_pump_system":
            room = HeatPumpRoomParameters(
                length=float(room_params.get('length', 5.0)),
                breadth=float(room_params.get('breadth', 4.0)),
                height=float(room_params.get('height', 2.5)),
                current_temp=float(room_params.get('current_temp', 25.0)),
                target_temp=float(room_params.get('target_temp', 22.0)),
                external_temp=float(room_params.get('external_temp', 35.0)),
                wall_insulation=room_params.get('wall_insulation', 'medium'),
                num_people=int(room_params.get('num_people', 0)),
                mode=room_params.get('mode', 'cooling'),
                humidity=float(room_params.get('humidity', 50.0)),
                heat_gain_external=float(
                    room_params.get('heat_gain_external', 0.0))
            )

            hvac = HeatPumpHVACParameters(
                power=float(hvac_params.get('power', 3.5)),
                cop=float(hvac_params.get('cop', 3.0)),
                air_flow_rate=float(hvac_params.get('air_flow_rate', 0.5)),
                supply_temp=float(hvac_params.get('supply_temp', 12.0)),
                fan_speed=float(hvac_params.get('fan_speed', 100.0)),
                time_interval=float(hvac_params.get('time_interval', 1.0))
            )

            return HeatPumpSystemSimulator(room, hvac)

        elif system_type == "vrf_system":
            room = VRFRoomParameters(
                length=float(room_params.get('length', 5.0)),
                breadth=float(room_params.get('breadth', 4.0)),
                height=float(room_params.get('height', 2.5)),
                current_temp=float(room_params.get('current_temp', 25.0)),
                target_temp=float(room_params.get('target_temp', 22.0)),
                external_temp=float(room_params.get('external_temp', 35.0)),
                wall_insulation=room_params.get('wall_insulation', 'medium'),
                num_people=int(room_params.get('num_people', 0)),
                mode=room_params.get('mode', 'cooling'),
                humidity=float(room_params.get('humidity', 50.0)),
                heat_gain_external=float(
                    room_params.get('heat_gain_external', 0.0))
            )

            hvac = VRFHVACParameters(
                power=float(hvac_params.get('power', 3.5)),
                cop=float(hvac_params.get('cop', 3.0)),
                air_flow_rate=float(hvac_params.get('air_flow_rate', 0.5)),
                supply_temp=float(hvac_params.get('supply_temp', 12.0)),
                fan_speed=float(hvac_params.get('fan_speed', 100.0)),
                time_interval=float(hvac_params.get('time_interval', 1.0))
            )

            return VRFSystemSimulator(room, hvac)

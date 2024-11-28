from enum import Enum
import json
import logging
from typing import List, Union
import broadlink
import questionary
from helpers import async_learn, validateNumber


# https://github.com/litinoveweedle/SmartIR/blob/master/docs/CODES_SYNTAX.md
# Climate operation commands
# operation mode -> preset mode -> fan mode -> swing mode -> temperature -> recorded IR command

class ClimateOperationModes(Enum):
    OFF = "off"
    AUTO = "auto"
    HEAT = "heat"
    COOL = "cool"
    HEAT_COOL = "heat_cool"
    FAN = "fan_only"
    DRY = "dry"

class ClimatePresetModes(Enum):
    NONE = "none"
    ECO = "eco"
    TURBO = "turbo"

class ClimateFanModes(Enum):
    AUTO = "auto"
    LEVEL1 = "level1"
    LEVEL2 = "level2"
    LEVEL3 = "level3"
    LEVEL4 = "level4"
    LEVEL5 = "level5"
    LEVEL6 = "level6"
    LEVEL7 = "level7"
    LEVEL8 = "level8"
    LEVEL9 = "level9"
    LEVEL10 = "level10"

class ClimateSwingModes(Enum):
    OFF = "off"
    HSWING = "horiz_swing"
    VSWING = "vert_swing"
    BOTH = "hv_swing"

class ClimateDevice:
    def __init__(
        self,
        device: Union[broadlink.rm4pro, broadlink.rm4mini],
        manufacturer: str,
        supportedModels: List[str],
        logger: logging.Logger,
    ):
        self.device = device
        self.operationModes = self._promptOperationModes()
        self.presetModes = self._promptPresetModes()
        self.fanModes = self._promptFanModes()
        self.swingModes = self._promptSwingModes()
        self.tempMin = self._promptTemperature("Minimum")
        self.tempMax = self._promptTemperature("Maximum")
        self.precision = self._promptPrecision()
        self.logger = logger

        # Grab our temps with precision, and trim the ending .0's
        tempWithPrecision = [
            self.tempMin + self.precision * i
            for i in range(int((self.tempMax - self.tempMin) / self.precision) + 1)
        ]
        self.temps = [int(x) if x.is_integer() else x for x in tempWithPrecision]

        self.outputConfig = self._buildBaseOutputConfig(manufacturer, supportedModels)

    def _promptOperationModes(self):
        # Remove OFF from the list of operation modes, its required below
        operationModes = [
            operationMode.value
            for operationMode in ClimateOperationModes
            if operationMode != ClimateOperationModes.OFF
        ]

        selectedOperationModes = questionary.checkbox(
            "Select Operation Modes",
            choices=operationModes
        ).ask()

        return selectedOperationModes

    def _promptPresetModes(self):
        selectedPresetModes = questionary.checkbox(
            "Select Preset Modes",
            choices=[presetMode.value for presetMode in ClimatePresetModes],
        ).ask()

        return selectedPresetModes

    def _promptFanModes(self):
        selectedFanModes = questionary.checkbox(
            "Select Fan Modes (Number of speeds supported)",
            choices=[fanMode.value for fanMode in ClimateFanModes],
        ).ask()

        return selectedFanModes

    def _promptSwingModes(self):
        selectedSwingModes = questionary.checkbox(
            "Select Fan Swing Modes",
            choices=[swingMode.value for swingMode in ClimateSwingModes],
        ).ask()

        return selectedSwingModes

    def _promptTemperature(self, minOrMax: str):
        temperature = questionary.text(
            f"Enter the {minOrMax} Temperature", validate=validateNumber
        ).ask()
        return int(temperature)

    def _promptPrecision(self):
        precision = questionary.select(
            "Select Precision (Default is 1.0)", choices=["1.0", "0.5"]
        ).ask()
        return float(precision)

    def _buildBaseOutputConfig(
        self,
        manufacturer: str,
        supportedModels: List[str],
    ):
        # Build the base output config
        outputConfig = {}
        outputConfig["manufacturer"] = manufacturer
        outputConfig["supportedModels"] = supportedModels
        outputConfig["supportedController"] = "Broadlink"
        outputConfig["commandsEncoding"] = "Base64"
        outputConfig["minTemperature"] = self.tempMin
        outputConfig["maxTemperature"] = self.tempMax
        outputConfig["precision"] = self.precision
        outputConfig["operationModes"] = self.operationModes
        outputConfig["presetModes"] = self.presetModes
        outputConfig["fanModes"] = self.fanModes
        outputConfig["swingModes"] = self.swingModes
        outputConfig["commands"] = {}

        # Build the base config for each operation mode
        for operationMode in self.operationModes:
            outputConfig["commands"][operationMode] = {}
            for presetMode in self.presetModes:
                outputConfig["commands"][operationMode][presetMode] = {}
                for fanMode in self.fanModes:
                    outputConfig["commands"][operationMode][presetMode][fanMode] = {}
                    for swingMode in self.swingModes:
                        outputConfig["commands"][operationMode][presetMode][fanMode][swingMode] = {}
                        for temp in self.temps:
                            outputConfig["commands"][operationMode][presetMode][fanMode][swingMode][str(temp)] = ""

        return outputConfig

    def _learnCommand(self, operationMode: str, presetMode: str, fanMode: str, swingMode: str, temp: int):
        if operationMode and fanMode and temp:
            print(
                f"Learning O = {operationMode.upper()} P = {presetMode.upper()} F = {fanMode.upper()} S = {swingMode.upper()}  {str(temp).upper()}°"
            )
        elif operationMode and fanMode:
            print(f"Learning {operationMode.upper()} {fanMode.upper()}")
        elif operationMode:
            print(f"Learning {operationMode.upper()}")

        command = async_learn(self.device)

        choice = input(f"Press Enter or Y to confirm or N to Relearn - {command}\n")

        if choice.lower() == "y" or choice == "":
            return self._writeCommandToConfig(command, operationMode, presetMode, fanMode, swingMode, temp)
        else:
            return self._learnCommand(operationMode, presetMode, fanMode, swingMode, temp)

    def _writeCommandToConfig(
            self, command: str, operationMode: str, presetMode: str, fanMode: str, swingMode: str, temp: int
    ):
        if operationMode and fanMode and temp:
            self.outputConfig["commands"][operationMode][presetMode][fanMode][swingMode][str(temp)] = command
        elif operationMode and fanMode:
            self.outputConfig["commands"][operationMode][None][fanMode][swingMode] = command
        elif operationMode:
            self.outputConfig["commands"][operationMode] = command

    def learn(self):
        print(
            "\nYou will now be prompted to press the corresponding button on the remote for each command\n"
        )

        # Learn the OFF Command
        self._learnCommand(ClimateOperationModes.OFF.name.lower(), None, None, None, None)
        self.logger.debug(json.dumps(self.outputConfig, indent=4))

        # Learn each temperature at each fanMode and operationMode
        for operationMode in self.operationModes:
            for presetMode in self.presetModes:
                for fanMode in self.fanModes:
                    for swingMode in self.swingModes:
                        for temp in self.temps:
                            self._learnCommand(operationMode, presetMode, fanMode, swingMode, temp)
                            self.logger.debug(json.dumps(self.outputConfig, indent=4))

        return self.outputConfig

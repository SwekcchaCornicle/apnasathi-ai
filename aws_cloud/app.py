#!/usr/bin/env python3
import json
from pathlib import Path

import aws_cdk as cdk

from apna_sathi_stack import ApnaSathiStack

parameters_path = Path(__file__).with_name("env_parameters.json")
with parameters_path.open(encoding="utf-8") as parameters_file:
    env_parameters = json.load(parameters_file)

app = cdk.App()
ApnaSathiStack(
    app,
    "ApnaSathiStack",
    env=cdk.Environment(
        account=env_parameters["account_no"],
        region=env_parameters["region"],
    )
)
app.synth()
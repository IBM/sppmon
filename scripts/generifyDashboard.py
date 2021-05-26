import re
from os.path import isfile, realpath, join
from typing import Any, Dict, List, Pattern

class GenerifyDashboard:


    def main(self):
        """Creates from the 14 day dashboard a new dashboard for an generic import.
        Alerts are transferred

        Raises:
            ValueError: error when reading or writing files
        """

        dashboardName: str = "SPPMON for IBM Spectrum Protect Plus.json"
        dasboardDir: str = realpath("../Grafana")
        dashboardPath: str = join(dasboardDir, dashboardName)

        genericVarName:str = r"DS_DATASOURCE"
        genericVar: str = r"${" + genericVarName + r"}"


        print(f"> Opening default dashboard folder: {dasboardDir}")
        print(f"> Editing default dashboard file: {dashboardName}")
        print(f"> trying to open dashboard on path {dashboardPath}")

        try:
            dashboardFile = open(dashboardPath, "rt")
            dashboardStr = dashboardFile.read()
            dashboardFile.close()
        except Exception as error:
            print(error)
            raise ValueError("> Error opening dashboard file. It seems like the default path to the dashboard is incorrect")

        print("> Sucessfully opened. Updating dashboard")

        if("__inputs" not in dashboardStr):
            raise ValueError("This is not a generic dashboard. Please make sure to export it with the box `export for externally` checked!")

        # get old var name
        oldVarName = re.search(r""""name":\s*"(.*?)"[,\s]*""", dashboardStr).group(1)
        oldVar = r"\${" + oldVarName + r"}"

        # replace first occurence with the new variable name
        dashboardStr = re.sub(
            fr""""name":\s*"{oldVarName}"\s*,""",
            fr""""name": "{genericVarName}",""",
            dashboardStr,
            1)
        # replace the label
        dashboardStr = re.sub(
            fr""""label":\s*".*?"\s*,""",
            fr""""label": "Datasource",""",
            dashboardStr,
            1)

        # replace dashboard name (there may be a name appended)
        dashboardStr = re.sub(
            r""""title":\s*"SPPMON for IBM Spectrum Protect Plus.*?"\s*,""",
            fr""""title": "SPPMON for IBM Spectrum Protect Plus {genericVar}",""",
            dashboardStr,
            1)

        # replace uid by new one
        dashboardStr = re.sub(
            r""""uid": ".*?"\s*,""",
            fr""""uid": "sppmon_single_view_DS_{genericVar}",""",
            dashboardStr,
            1)

        # replace all occurences of the old variable
        dashboardStr = re.sub(
            fr"""{oldVar}""",
            fr"""{genericVar}""",
            dashboardStr
        )

        print("> finished updating dashboard")
        print("> trying to write updated dashboard back into original file")
        try:
            dashboard_file = open(dashboardPath, "wt")
            dashboard_file.write(dashboardStr)
            dashboard_file.close()
        except Exception as error:
            print(error)
            raise ValueError("Error creating new dashboard file.")
        print("> Sucessfully updated dashboard file.")


if __name__ == "__main__":
    GenerifyDashboard().main()
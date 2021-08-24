"""
(C) IBM Corporation 2021

Description:
    Generifies a dashboard for external use by stripping of datasource informations.
    To be used by developers before sharing the dashboard.

Repository:
  https://github.com/IBM/spectrum-protect-sppmon

Author:
 Niels Korschinsky
"""

import re
import sys
from utils import Utils
from os.path import isfile, realpath, join, dirname


class GenerifyDashboard:
    """Generifies a dashboard for external use by stripping of datasource informations.
    To be used by developers before sharing the dashboard.
    """

    def main(self):
        """Creates from the 14 day dashboard a new dashboard for an generic import.
        Alerts are transferred.

        Raises:
            ValueError: error when reading or writing files
        """

        scriptDirPath = dirname(sys.argv[0])
        dashboardName: str = "SPPMON for IBM Spectrum Protect Plus.json"
        dashboardDir: str = realpath(join(scriptDirPath, "..", "Grafana"))
        dashboardPath: str = join(dashboardDir, dashboardName)

        genericVarName: str = r"DS_DATASOURCE"
        genericVar: str = r"${" + genericVarName + r"}"

        print(f"> Opening default dashboard folder: {dashboardDir}")
        print(f"> Editing default dashboard file: {dashboardName}")
        print(f"> trying to open dashboard on path {dashboardPath}")

        if(not isfile(dashboardPath)):
            raise ValueError(
                f"> The Path is incorrect, is not a file: {dashboardPath}")

        try:
            dashboardFile = open(dashboardPath, "rt")
            dashboardStr = dashboardFile.read()
            dashboardFile.close()
        except Exception as error:
            print(error)
            raise ValueError(
                "> Error opening dashboard file. It seems like the default path to the dashboard is incorrect")

        print("> Sucessfully opened. Updating dashboard")

        if("__inputs" not in dashboardStr):
            raise ValueError(
                "This is not a generic dashboard. " +
                "Please make sure to export it with the box `export for externally` checked!")

        # get old var name
        oldVarName = re.search(
            r""""name":\s*"(.*?)"[,\s]*""", dashboardStr).group(1)

        if(oldVarName == 'DS_DATASOURCE'):
            Utils.printRow()
            print("ERROR: The Dashboard is probably already generified. Aborting.\n")
            exit(1)

        oldVarEscaped = r"\${" + oldVarName + r"}"

        # replace first occurence with the new variable name
        dashboardStr = re.sub(
            fr""""name":\s*"{oldVarName}"\s*,""",
            fr""""name": "{genericVarName}",""",
            dashboardStr,
            1)
        # replace the label
        oldDsName = re.search(
            r""""label":\s*"(.*?)"[,\s]*""", dashboardStr).group(1)

        dashboardStr = re.sub(
            fr""""label":\s*"{oldDsName}"\s*,""",
            fr""""label": "Datasource",""",
            dashboardStr,
            1)

        # replace dashboard name (there may be a name appended)
        dashboardStr = re.sub(
            r""""title":\s*"SPPMON for IBM Spectrum Protect Plus\s*(?:(?!14-Day Dashboards).)+?\s*"\s*,""",
            fr""""title": "SPPMON for IBM Spectrum Protect Plus {genericVar}",""",
            dashboardStr)

        # replace uid by new one
        dashboardStr = re.sub(
            r""""uid": ".*?"\s*,""",
            fr""""uid": "sppmon_single_view_DS_{genericVar}",""",
            dashboardStr,
            1)

        # replace all occurences of the old variable
        dashboardStr = re.sub(
            fr"""{oldVarEscaped}""",
            fr"""{genericVar}""",
            dashboardStr
        )

        dashboardStr = re.sub(
            fr"""{oldDsName}""",
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
            Utils.printRow()
            print(error)
            raise ValueError("Error creating new dashboard file.")
        Utils.printRow()
        print("> Sucessfully updated dashboard file.")
        print("> Script finished")


if __name__ == "__main__":
    GenerifyDashboard().main()

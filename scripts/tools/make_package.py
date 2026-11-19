"""
Generates an SSIS package (.dtsx) that follows the project's standard pattern:

    SQL Start Run  ->  EPT <python script>  ->  SQL step 1 -> ... -> SQL step n  ->  SQL End Run Success
    OnError event handler  ->  SQL End Run Failed (with the error text)

- Logging uses DWH_DB.etl.usp_StartRun / usp_EndRun (Phase 0).
- Package variables ProjectRoot / PythonExe (same values as the project parameters) let the
  package run with DTExec /F without building the project.
- The last SQL step that returns a column "RowsLoaded" sets User::RowsLoaded for the log.

Used by scripts/tools/build_packages.py. Each package gets fresh GUIDs.
"""
import uuid
from xml.sax.saxutils import escape, quoteattr

CONN = {"DWH_DB": "DWH_DB", "Staging_DB": "Staging_DB"}


def _g() -> str:
    return "{" + str(uuid.uuid4()).upper() + "}"


def _sql_task(ref_prefix, name, desc, conn_id, static_sql, expr=None, bind_rows=False, single_row=None):
    single = bind_rows if single_row is None else single_row
    prop = (f'      <DTS:PropertyExpression DTS:Name="SqlStatementSource">{escape(expr)}</DTS:PropertyExpression>\n'
            if expr else "")
    result_type = ' SQLTask:ResultType="ResultSetType_SingleRow"' if single else ""
    binding = ""
    if bind_rows:
        binding = '\n          <SQLTask:ResultBinding SQLTask:ResultName="RowsLoaded" SQLTask:DtsVariableName="User::RowsLoaded" />'
    elif single:
        binding = '\n          <SQLTask:ResultBinding SQLTask:ResultName="RunID" SQLTask:DtsVariableName="User::RunID" />'
    return f'''    <DTS:Executable
      DTS:refId="{ref_prefix}\\{name}"
      DTS:CreationName="Microsoft.ExecuteSQLTask"
      DTS:Description={quoteattr(desc)}
      DTS:DTSID="{_g()}"
      DTS:ExecutableType="Microsoft.ExecuteSQLTask"
      DTS:LocaleID="-1"
      DTS:ObjectName={quoteattr(name)}
      DTS:ThreadHint="0">
      <DTS:Variables />
{prop}      <DTS:ObjectData>
        <SQLTask:SqlTaskData
          SQLTask:Connection="{conn_id}"
          SQLTask:SqlStatementSource={quoteattr(static_sql)}{result_type}
          xmlns:SQLTask="www.microsoft.com/sqlserver/dts/tasks/sqltask">{binding}
        </SQLTask:SqlTaskData>
      </DTS:ObjectData>
    </DTS:Executable>
'''


def make_package(name, description, python_script, sql_steps, root=r"D:\DroughtProject",
                 python_exe=r"D:\DroughtProject\venv\Scripts\python.exe"):
    """
    sql_steps: list of dicts
        name, desc, conn ('DWH_DB' or 'Staging_DB'), sql (static text),
        expr (optional SSIS expression for the statement), rows (True if it returns RowsLoaded)
    python_script: file name in scripts/ (or None for no Python step)
    """
    conn_ids = {k: _g() for k in CONN}
    tasks, order = [], []

    tasks.append(_sql_task("Package", "SQL Start Run", "Calls etl.usp_StartRun and stores the RunID",
                           conn_ids["DWH_DB"],
                           f"DECLARE @id INT; EXEC etl.usp_StartRun @PackageName = N'{name}', @RunID = @id OUTPUT; SELECT @id AS RunID;",
                           expr='"DECLARE @id INT; EXEC etl.usp_StartRun @PackageName = N\'" + @[System::PackageName] + "\', @RunID = @id OUTPUT; SELECT @id AS RunID;"',
                           single_row=True))
    order.append("SQL Start Run")

    scripts = [python_script] if isinstance(python_script, str) else list(python_script or [])
    for python_script in scripts:
        # task names can't contain / \ : [ ] . =  -> "EPT Run 04_faostat"
        ept = f"EPT Run {python_script.rsplit('.', 1)[0]}"
        args_static = f'"{root}\\scripts\\{python_script}" "{root}"'
        args_expr = f'"\\"" + @[User::ProjectRoot] + "\\\\scripts\\\\{python_script}\\" \\"" + @[User::ProjectRoot] + "\\""'
        tasks.append(f'''    <DTS:Executable
      DTS:refId="Package\\{ept}"
      DTS:CreationName="Microsoft.ExecuteProcess"
      DTS:Description={quoteattr("Runs scripts\\" + python_script + "; fails if the script returns a non-zero exit code")}
      DTS:DTSID="{_g()}"
      DTS:ExecutableType="Microsoft.ExecuteProcess"
      DTS:LocaleID="-1"
      DTS:ObjectName={quoteattr(ept)}
      DTS:ThreadHint="0">
      <DTS:Variables />
      <DTS:PropertyExpression DTS:Name="Executable">@[User::PythonExe]</DTS:PropertyExpression>
      <DTS:PropertyExpression DTS:Name="Arguments">{escape(args_expr)}</DTS:PropertyExpression>
      <DTS:PropertyExpression DTS:Name="WorkingDirectory">@[User::ProjectRoot]</DTS:PropertyExpression>
      <DTS:ObjectData>
        <ExecuteProcessData
          Executable={quoteattr(python_exe)}
          Arguments={quoteattr(args_static)}
          WorkingDirectory={quoteattr(root)}
          FailTaskIfReturnCodeIsNotSuccessValue="True"
          SuccessValue="0" />
      </DTS:ObjectData>
    </DTS:Executable>
''')
        order.append(ept)

    for s in sql_steps:
        tasks.append(_sql_task("Package", s["name"], s["desc"], conn_ids[s["conn"]], s["sql"],
                               expr=s.get("expr"), bind_rows=s.get("rows", False)))
        order.append(s["name"])

    tasks.append(_sql_task("Package", "SQL End Run Success", "Calls etl.usp_EndRun with Success and the row count",
                           conn_ids["DWH_DB"], "SELECT 1;",
                           expr='"EXEC etl.usp_EndRun @RunID = " + (DT_WSTR, 12) @[User::RunID] + ", @Status = \'Success\', @RowsLoaded = " + (DT_WSTR, 12) @[User::RowsLoaded] + ";"'))
    order.append("SQL End Run Success")

    constraints = "".join(
        f'    <DTS:PrecedenceConstraint DTS:refId="Package.PrecedenceConstraints[C{i}]" DTS:CreationName="" '
        f'DTS:DTSID="{_g()}" DTS:From={quoteattr("Package\\" + a)} DTS:LogicalAnd="True" '
        f'DTS:ObjectName="C{i}" DTS:To={quoteattr("Package\\" + b)} />\n'
        for i, (a, b) in enumerate(zip(order, order[1:]), start=1))

    on_error = _sql_task("Package.EventHandlers[OnError]", "SQL End Run Failed",
                         "Calls etl.usp_EndRun with Failed and the error text", conn_ids["DWH_DB"], "SELECT 1;",
                         expr='"EXEC etl.usp_EndRun @RunID = " + (DT_WSTR, 12) @[User::RunID] + ", @Status = \'Failed\', @RowsLoaded = 0, @ErrorMessage = N\'" + SUBSTRING(REPLACE(@[System::ErrorDescription], "\'", "\'\'"), 1, 3500) + "\';"')

    def conn_xml(key):
        return f'''    <DTS:ConnectionManager
      DTS:refId="Package.ConnectionManagers[{key}]"
      DTS:CreationName="OLEDB"
      DTS:DTSID="{conn_ids[key]}"
      DTS:ObjectName="{key}">
      <DTS:ObjectData>
        <DTS:ConnectionManager
          DTS:ConnectionString="Data Source=localhost;Initial Catalog={key};Provider=MSOLEDBSQL;Integrated Security=SSPI;Trust Server Certificate=True;Auto Translate=False;Application Name=SSIS-{name};" />
      </DTS:ObjectData>
    </DTS:ConnectionManager>
'''

    def var(vname, dtype, value):
        return (f'    <DTS:Variable DTS:CreationName="" DTS:DTSID="{_g()}" DTS:IncludeInDebugDump="2345" '
                f'DTS:Namespace="User" DTS:ObjectName="{vname}">\n'
                f'      <DTS:VariableValue DTS:DataType="{dtype}">{escape(value)}</DTS:VariableValue>\n'
                f'    </DTS:Variable>\n')

    return f'''<?xml version="1.0"?>
<DTS:Executable xmlns:DTS="www.microsoft.com/SqlServer/Dts"
  DTS:refId="Package"
  DTS:CreationDate="11/18/2026 18:00:00"
  DTS:CreationName="Microsoft.Package"
  DTS:Description={quoteattr(description)}
  DTS:DTSID="{_g()}"
  DTS:ExecutableType="Microsoft.Package"
  DTS:LastModifiedProductVersion="17.0.1000.7"
  DTS:LocaleID="1033"
  DTS:ObjectName="{name}"
  DTS:PackageType="5"
  DTS:VersionBuild="1"
  DTS:VersionGUID="{_g()}">
  <DTS:Property DTS:Name="PackageFormatVersion">8</DTS:Property>
  <DTS:ConnectionManagers>
{conn_xml("DWH_DB")}{conn_xml("Staging_DB")}  </DTS:ConnectionManagers>
  <DTS:Variables>
{var("ProjectRoot", 8, root)}{var("PythonExe", 8, python_exe)}{var("RunID", 3, "0")}{var("RowsLoaded", 3, "0")}  </DTS:Variables>
  <DTS:Executables>
{"".join(tasks)}  </DTS:Executables>
  <DTS:PrecedenceConstraints>
{constraints}  </DTS:PrecedenceConstraints>
  <DTS:EventHandlers>
    <DTS:EventHandler
      DTS:refId="Package.EventHandlers[OnError]"
      DTS:CreationName="OnError"
      DTS:DTSID="{_g()}"
      DTS:EventID="0"
      DTS:EventName="OnError"
      DTS:LocaleID="-1">
      <DTS:Variables />
      <DTS:Executables>
{on_error}      </DTS:Executables>
    </DTS:EventHandler>
  </DTS:EventHandlers>
</DTS:Executable>
'''


def bulk_insert_step(table, csv_name, conn="Staging_DB"):
    """Standard staging step: empty the table and BULK INSERT the CSV from clean/."""
    with_opts = "WITH (FIRSTROW = 2, FIELDTERMINATOR = ';', ROWTERMINATOR = '0x0a', CODEPAGE = '65001', TABLOCK)"
    static = (f"SET NOCOUNT ON; TRUNCATE TABLE {table}; BULK INSERT {table} FROM "
              f"'D:\\DroughtProject\\clean\\{csv_name}' {with_opts};")
    expr = (f'"SET NOCOUNT ON; TRUNCATE TABLE {table}; BULK INSERT {table} FROM \'" + @[User::ProjectRoot] + '
            f'"\\\\clean\\\\{csv_name}\' {with_opts};"')
    return {"name": f"SQL Load Staging {table.split('.')[-1]}",
            "desc": f"Empties {table} and BULK INSERTs clean\\{csv_name}",
            "conn": conn, "sql": static, "expr": expr}

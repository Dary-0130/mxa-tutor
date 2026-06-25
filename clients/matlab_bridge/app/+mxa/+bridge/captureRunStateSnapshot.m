function payload = captureRunStateSnapshot(simulationOutput, sessionId, runSequence, requestId, runId)
%CAPTURERUNSTATESNAPSHOT Whitelist-read a Simulink SimulationOutput run-state snapshot.

if nargin < 4
    requestId = char(java.util.UUID.randomUUID);
end
if nargin < 5
    runId = char(java.util.UUID.randomUUID);
end

if ~isa(simulationOutput, "Simulink.SimulationOutput")
    error("mxa:bridge:RunStateUnsupportedInput", ...
        "run-state input must be Simulink.SimulationOutput.");
end
validateRunSequence(runSequence);

metadata = readProperty(simulationOutput, "SimulationMetadata");
executionInfo = readProperty(metadata, "ExecutionInfo");
timingInfo = readProperty(metadata, "TimingInfo");
modelInfo = readProperty(metadata, "ModelInfo");

[runStatus, stopReason] = readRunStatus(executionInfo);
solver = readSolver(modelInfo);
metrics = collectMetrics(simulationOutput, executionInfo, timingInfo, modelInfo);
series = collectSeries(simulationOutput);

payload = struct();
payload.protocol_version = char(mxa.bridge.MatlabBridgeApp.RunStateProtocolVersion);
payload.request_id = char(requestId);
payload.session_id = char(sessionId);
payload.run_id = char(runId);
payload.run_sequence = int32(runSequence);
payload.matlab_release = char("R" + string(version("-release")));
payload.client_version = char(mxa.bridge.MatlabBridgeApp.ClientVersion);
payload.run_state_sharing_consent_confirmed = true;
payload.consent_notice_version = char(mxa.bridge.MatlabBridgeApp.RunStateConsentNoticeVersion);
payload.run_status = char(runStatus);
payload.convergence_status = "not_applicable";
if strlength(stopReason) > 0
    payload.stop_reason = char(mxa.bridge.redactRunStateString(stopReason, 160, 480));
end
if strlength(solver) > 0
    payload.solver = char(mxa.bridge.redactRunStateString(solver, 32, 96));
end
if isempty(metrics)
    payload.metrics_status = "unavailable";
    payload.metrics = {};
else
    payload.metrics_status = "available";
    payload.metrics = metrics;
end
if isempty(series)
    payload.series_status = "unavailable";
    payload.series = {};
else
    payload.series_status = "available";
    payload.series = series;
end
end

function validateRunSequence(value)
if ~(isnumeric(value) && isscalar(value) && isfinite(value) && floor(value) == value)
    error("mxa:bridge:RunStateInvalidSequence", "run_sequence must be an integer.");
end
if value < 0 || value > 1000000
    error("mxa:bridge:RunStateInvalidSequence", "run_sequence is out of range.");
end
end

function [runStatus, stopReason] = readRunStatus(executionInfo)
stopEvent = readTextProperty(executionInfo, "StopEvent");
errorDiagnostic = readProperty(executionInfo, "ErrorDiagnostic");
normalized = lower(regexprep(stopEvent, "\s+", ""));
if contains(normalized, "diagnostic") || ~isempty(errorDiagnostic)
    runStatus = "execution_error";
elseif contains(normalized, "reachedstoptime")
    runStatus = "completed";
elseif strlength(stopEvent) > 0
    runStatus = "stopped";
else
    runStatus = "unknown";
end
stopReason = stopEvent;
end

function solver = readSolver(modelInfo)
solver = "";
solverInfo = readProperty(modelInfo, "SolverInfo");
solverName = readTextProperty(solverInfo, "SolverName");
solverType = readTextProperty(solverInfo, "SolverType");
if strlength(solverType) > 0 && strlength(solverName) > 0
    solver = solverType + ":" + solverName;
elseif strlength(solverName) > 0
    solver = solverName;
elseif strlength(solverType) > 0
    solver = solverType;
end
end

function metrics = collectMetrics(simulationOutput, executionInfo, timingInfo, modelInfo)
metrics = {};
names = strings(0, 1);
[metrics, names] = addNumericMetric(metrics, names, "stop_event_time", ...
    readProperty(executionInfo, "StopEventTime"), "known", "s");
[metrics, names] = addNumericMetric(metrics, names, "wall_clock_elapsed", ...
    readFirstNumericProperty(timingInfo, ...
    ["ExecutionElapsedWallTime", "TotalElapsedWallTime", "SimulationElapsedWallTime"]), ...
    "known", "s");

solverInfo = readProperty(modelInfo, "SolverInfo");
[metrics, names] = addNumericMetric(metrics, names, "solver_max_step", ...
    readFirstNumericProperty(solverInfo, ["MaxStep", "MaxStepSize"]), "known", "s");

outputNames = readOutputNames(simulationOutput);
for index = 1:numel(outputNames)
    if numel(metrics) >= 16
        return
    end
    value = readOutputValue(simulationOutput, outputNames(index));
    if isnumeric(value) && isscalar(value) && isfinite(value)
        [metrics, names] = addNumericMetric(metrics, names, outputNames(index), ...
            double(value), "unknown", "");
    end
end
end

function [metrics, names] = addNumericMetric(metrics, names, name, value, unitStatus, unit)
if numel(metrics) >= 16 || isempty(value)
    return
end
if ~(isnumeric(value) && isscalar(value) && isfinite(value))
    return
end
metricName = mxa.bridge.redactRunStateString(name, 32, 96);
if any(names == metricName)
    return
end
metric = struct();
metric.name = char(metricName);
metric.value = double(value);
metric.unit_status = char(unitStatus);
if string(unitStatus) == "known"
    metric.unit = char(mxa.bridge.redactRunStateString(unit, 16, 48));
end
metrics{end + 1} = metric; %#ok<AGROW>
names(end + 1, 1) = metricName; %#ok<AGROW>
end

function series = collectSeries(simulationOutput)
series = {};
seriesIds = strings(0, 1);
outputNames = readOutputNames(simulationOutput);
for index = 1:numel(outputNames)
    if numel(series) >= 4
        return
    end
    value = readOutputValue(simulationOutput, outputNames(index));
    [series, seriesIds] = collectSeriesFromValue(series, seriesIds, outputNames(index), value);
end
end

function [series, seriesIds] = collectSeriesFromValue(series, seriesIds, baseName, value)
if isa(value, "timeseries")
    [series, seriesIds] = addTimeseries(series, seriesIds, baseName, baseName, value);
    return
end
if ~isa(value, "Simulink.SimulationData.Dataset")
    return
end
elementCount = readDatasetElementCount(value);
for elementIndex = 1:elementCount
    if numel(series) >= 4
        return
    end
    try
        element = value.getElement(elementIndex);
    catch
        continue
    end
    elementName = readTextProperty(element, "Name");
    if strlength(elementName) == 0
        elementName = string(baseName) + "_" + string(elementIndex);
    end
    values = readProperty(element, "Values");
    if isa(values, "timeseries")
        [series, seriesIds] = addTimeseries(series, seriesIds, elementName, elementName, values);
    end
end
end

function [series, seriesIds] = addTimeseries(series, seriesIds, seriesId, label, ts)
if numel(series) >= 4
    return
end
time = readProperty(ts, "Time");
data = readProperty(ts, "Data");
if isempty(time) || isempty(data) || ~isnumeric(time) || ~isnumeric(data) || ~isvector(data)
    return
end
timeUnit = readTimeUnit(ts);
[valueUnitStatus, valueUnit] = readValueUnit(ts);
summary = mxa.bridge.summarizeRunStateSeries( ...
    seriesId, label, time, data, timeUnit, valueUnitStatus, valueUnit);
if isempty(summary)
    return
end
if any(seriesIds == string(summary.series_id))
    return
end
series{end + 1} = summary; %#ok<AGROW>
seriesIds(end + 1, 1) = string(summary.series_id); %#ok<AGROW>
end

function names = readOutputNames(simulationOutput)
names = strings(0, 1);
try
    rawNames = simulationOutput.who;
catch
    return
end
names = string(rawNames(:));
if numel(names) > 32
    names = names(1:32);
end
end

function value = readOutputValue(simulationOutput, name)
value = [];
try
    value = simulationOutput.get(char(name));
catch
    value = [];
end
end

function count = readDatasetElementCount(dataset)
count = 0;
try
    count = dataset.numElements;
catch
    try
        count = numel(dataset);
    catch
        count = 0;
    end
end
count = min(double(count), 16);
end

function timeUnit = readTimeUnit(ts)
timeUnit = "unknown";
timeInfo = readProperty(ts, "TimeInfo");
units = readTextProperty(timeInfo, "Units");
switch lower(strip(units))
    case {"s", "sec", "secs", "second", "seconds"}
        timeUnit = "s";
    case {"ms", "millisecond", "milliseconds"}
        timeUnit = "ms";
    case {"us", "microsecond", "microseconds"}
        timeUnit = "us";
end
end

function [unitStatus, unit] = readValueUnit(ts)
unitStatus = "unknown";
unit = "";
dataInfo = readProperty(ts, "DataInfo");
units = strip(readTextProperty(dataInfo, "Units"));
if strlength(units) > 0
    unitStatus = "known";
    unit = units;
end
end

function value = readFirstNumericProperty(item, propertyNames)
value = [];
for index = 1:numel(propertyNames)
    candidate = readProperty(item, propertyNames(index));
    if isnumeric(candidate) && isscalar(candidate) && isfinite(candidate)
        value = double(candidate);
        return
    end
end
end

function value = readProperty(item, propertyName)
value = [];
try
    if isstruct(item) || isobject(item)
        value = item.(char(propertyName));
    end
catch
    value = [];
end
end

function value = readTextProperty(item, propertyName)
rawValue = readProperty(item, propertyName);
if isempty(rawValue)
    value = "";
else
    value = strjoin(splitlines(string(rawValue)), " ");
end
end

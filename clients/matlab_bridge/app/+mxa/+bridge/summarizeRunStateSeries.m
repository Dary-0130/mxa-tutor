function series = summarizeRunStateSeries(seriesId, label, time, data, timeUnit, valueUnitStatus, valueUnit)
%SUMMARIZERUNSTATESERIES Build a bounded uniform run-state series summary.

if nargin < 5
    timeUnit = "unknown";
end
if nargin < 6
    valueUnitStatus = "unknown";
end
if nargin < 7
    valueUnit = "";
end

series = [];
time = double(time(:));
data = double(data(:));
if numel(time) ~= numel(data) || numel(time) < 2
    return
end
if any(~isfinite(time)) || any(~isfinite(data))
    return
end

deltas = diff(time);
if any(deltas <= 0)
    return
end
medianDelta = median(deltas);
relTol = 1e-6;
if medianDelta <= 0 || max(abs(deltas - medianDelta)) > relTol * medianDelta
    return
end

sourcePointCount = numel(time);
seriesId = sanitizeSeriesId(seriesId);
label = mxa.bridge.redactRunStateString(label, 32, 96);
timeUnit = normalizeTimeUnit(timeUnit);
valueUnitStatus = normalizeUnitStatus(valueUnitStatus);

if sourcePointCount <= 192
    series = struct();
    series.representation = "identity_uniform_v1";
    series.series_id = char(seriesId);
    series.label = char(label);
    series.time_unit = char(timeUnit);
    series.value_unit_status = char(valueUnitStatus);
    if valueUnitStatus == "known"
        series.value_unit = char(mxa.bridge.redactRunStateString(valueUnit, 16, 48));
    end
    series.sample_order = "chronological";
    series.source_point_count = int32(sourcePointCount);
    series.t_start = time(1);
    series.t_step = medianDelta;
    series.y = reshape(data, 1, []);
    return
end

bucketCount = 96;
tStart = time(1);
bucketWidth = (time(end) - tStart) / bucketCount;
if bucketWidth <= 0 || ~isfinite(bucketWidth)
    return
end

yMin = inf(1, bucketCount);
yMax = -inf(1, bucketCount);
for index = 1:sourcePointCount
    bucketIndex = min(bucketCount, floor((time(index) - tStart) / bucketWidth) + 1);
    yMin(bucketIndex) = min(yMin(bucketIndex), data(index));
    yMax(bucketIndex) = max(yMax(bucketIndex), data(index));
end
if any(isinf(yMin)) || any(isinf(yMax))
    return
end

series = struct();
series.representation = "min_max_envelope_uniform_v1";
series.series_id = char(seriesId);
series.label = char(label);
series.time_unit = char(timeUnit);
series.value_unit_status = char(valueUnitStatus);
if valueUnitStatus == "known"
    series.value_unit = char(mxa.bridge.redactRunStateString(valueUnit, 16, 48));
end
series.sample_order = "chronological";
series.source_point_count = int32(sourcePointCount);
series.t_start = tStart;
series.bucket_width = bucketWidth;
series.y_min = yMin;
series.y_max = yMax;
end

function value = sanitizeSeriesId(value)
value = string(value);
value = regexprep(value, '[^A-Za-z0-9._-]', '_');
value = strip(value);
if strlength(value) == 0
    value = "series";
end
if strlength(value) > 32
    value = extractBefore(value, 33);
end
end

function value = normalizeTimeUnit(value)
value = lower(strip(string(value)));
switch value
    case {"s", "sec", "secs", "second", "seconds"}
        value = "s";
    case {"ms", "millisecond", "milliseconds"}
        value = "ms";
    case {"us", "microsecond", "microseconds"}
        value = "us";
    otherwise
        value = "unknown";
end
end

function value = normalizeUnitStatus(value)
value = lower(strip(string(value)));
if ~ismember(value, ["known", "unknown", "not_applicable"])
    value = "unknown";
end
end

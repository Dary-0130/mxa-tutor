function response = postRunState(baseUrl, frozenJson, timeoutSeconds)
%POSTRUNSTATE Send a frozen run-state JSON payload to the bridge endpoint.

mxa.bridge.validateBaseUrl(baseUrl);
base = char(strip(string(baseUrl)));
while endsWith(base, "/")
    base = base(1:end-1);
end
endpoint = char(string(base) + "/api/v1/bridge/run-state");
options = weboptions( ...
    "MediaType", "application/json", ...
    "Timeout", timeoutSeconds);

response = webwrite(endpoint, char(frozenJson), options);
end

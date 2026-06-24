function response = postRunState(baseUrl, frozenJson, timeoutSeconds, accessToken)
%POSTRUNSTATE Send a frozen run-state JSON payload to the bridge endpoint.

mxa.bridge.validateBaseUrl(baseUrl);
base = char(strip(string(baseUrl)));
while endsWith(base, "/")
    base = base(1:end-1);
end
endpoint = char(string(base) + "/api/v1/bridge/run-state");
tokenText = string(accessToken);
if strlength(tokenText) == 0
    error("mxa:bridge:AuthTokenMissing", "run-state access token is required.");
end
options = weboptions( ...
    "MediaType", "application/json", ...
    "HeaderFields", ["Authorization", "Bearer " + tokenText], ...
    "Timeout", timeoutSeconds);

response = webwrite(endpoint, char(frozenJson), options);
end

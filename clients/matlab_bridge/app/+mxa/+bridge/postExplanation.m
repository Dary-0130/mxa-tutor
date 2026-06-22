function response = postExplanation(baseUrl, payload, timeoutSeconds)
%POSTEXPLANATION Send a manual diagnostic payload to the explanation endpoint.

mxa.bridge.validateBaseUrl(baseUrl);
base = char(strip(string(baseUrl)));
while endsWith(base, "/")
    base = base(1:end-1);
end
endpoint = char(string(base) + "/api/v1/bridge/explanation");
options = weboptions( ...
    "MediaType", "application/json", ...
    "Timeout", timeoutSeconds);

response = webwrite(endpoint, payload, options);
end

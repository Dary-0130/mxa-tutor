function app = mxaMatlabBridgeApp(varargin)
%MXAMATLABBRIDGEAPP Launch the MXA MATLAB bridge app.
%
% The optional name-value arguments are intentionally narrow so tests can
% inject a localhost base URL and confirmation behavior without global state.

app = mxa.bridge.MatlabBridgeApp(varargin{:});
end

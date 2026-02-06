# apick demo — fzf-powered OpenAPI API client
# Regenerate with: vhs demo.tape

Output demo.gif

Set Shell "bash"
Set FontSize 16
Set Width 1200
Set Height 700
Set Padding 20
Set TypingSpeed 30ms
Set Theme "Catppuccin Mocha"
Set WindowBar Colorful
Set WindowBarSize 40

Sleep 500ms

# Launch apick with the Petstore OpenAPI spec
Type "uv run apick https://petstore3.swagger.io/api/v3/openapi.json"
Sleep 300ms
Enter

# Wait for uv startup + spec download + fzf to appear
Sleep 8s

# Search for GET /pet/{petId}
Type "GET petId"
Sleep 1s

# Select the endpoint
Enter
Sleep 2s

# Enter the petId path parameter
Type "7"
Sleep 200ms
Enter

# Wait for the API response
Sleep 3s

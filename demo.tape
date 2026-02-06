# apick demo — fzf-powered OpenAPI API client
# Regenerate with: vhs demo.tape

Output demo.gif

Set Shell "bash"
Set FontSize 16
Set Width 1200
Set Height 700
Set Padding 20
Set TypingSpeed 50ms
Set Theme "Catppuccin Mocha"
Set WindowBar Colorful
Set WindowBarSize 40

Sleep 500ms

# Launch apick with the Petstore OpenAPI spec
Type "apick https://petstore3.swagger.io/api/v3/openapi.json"
Sleep 300ms
Enter

# Wait for spec download + fzf to appear
Sleep 6s

# Browse endpoints (scroll down to show the list)
Down
Sleep 300ms
Down
Sleep 300ms
Down
Sleep 300ms
Down
Sleep 500ms

# Search for GET /pet/{petId}
Type "GET petId"
Sleep 2s

# Select the endpoint
Enter
Sleep 1.5s

# Enter the petId path parameter
Type "7"
Sleep 300ms
Enter

# Wait for the API response
Sleep 5s

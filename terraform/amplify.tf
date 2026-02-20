# -----------------------------------------------------------------------------
# Amplify frontend: deploy the ../amplify app via Amplify Console or CLI.
# (Terraform cannot create an Amplify app without a Git repository + token.)
# Set VITE_API_URL in the frontend to the API Gateway URL below.
# -----------------------------------------------------------------------------

# Outputs api_gateway_url and generate_brief_invoke_url are in outputs.tf.
# For the React app in ../amplify, set:
#   VITE_API_URL = terraform output -raw api_gateway_url

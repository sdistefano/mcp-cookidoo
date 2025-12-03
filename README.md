## Cookidoo MCP Server

An MCP (Model Context Protocol) server for interacting with the Thermomix Cookidoo platform, built with `fastmcp`.

> **Disclaimer:** This is an unofficial project. The developers are not affiliated with, endorsed by, or connected to Cookidoo, Vorwerk, Thermomix, or any of their subsidiaries or trademarks.

### Features

- **Authentication**: Connect to your Cookidoo account securely
- **Recipe Details**: Fetch detailed recipe information by ID
- **Recipe Generation**: Structure new custom recipes
- **Recipe Upload**: Upload custom recipes to your Cookidoo account
- **Custom Recipe Listing**: List your created (customer) recipes from Cookidoo
- **Custom Recipe Update**: Update existing custom recipes in place

### Setup

1. **Clone the repository and navigate to the project directory**

2. **Create a virtual environment and activate it:**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On macOS/Linux
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure your credentials and cookie:**

   ```bash
   cp .env.example .env
   # Edit .env with your Cookidoo credentials
   # COOKIDOO_EMAIL=...
   # COOKIDOO_PASSWORD=...
   #
   # Optional but recommended for listing existing custom recipes:
   # COOKIDOO_COOKIE=<full browser cookie string for cookidoo.fr>
   ```

   - **COOKIDOO_EMAIL / COOKIDOO_PASSWORD** are used by `cookidoo-api` for the official API login.
   - **COOKIDOO_COOKIE** (optional) is used only to scrape the `created-recipes` HTML page for your customer recipes.  
     You can copy this from your browser dev tools while logged into `cookidoo.fr`.

5. **Run the MCP server:**

   ```bash
   fastmcp run server.py
   ```

### Available Tools

- `connect_to_cookidoo` - Authenticate with Cookidoo
- `get_recipe_details` - Get detailed recipe by ID
- `generate_recipe_structure` - Structure a new recipe
- `upload_custom_recipe` - Upload a recipe to Cookidoo
- `list_custom_recipes` - List your custom (customer) recipes via HTML scraping
- `update_custom_recipe` - Update an existing custom recipe using a validated JSON structure

### Acknowledgments

This project is built on top of the `[cookidoo-api](https://github.com/miaucl/cookidoo-api)`, which provides the Python interface to interact with the Cookidoo platform. Special thanks for making this integration possible!

### License

MIT

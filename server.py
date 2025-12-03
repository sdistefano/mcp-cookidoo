"""
Cookidoo MCP Server

Main server file containing MCP tool definitions for interacting with Cookidoo.
"""

from fastmcp import FastMCP
from cookidoo_service import CookidooService, load_cookidoo_credentials
from schemas import CustomRecipe
from annotations import instructions_to_steps, text_steps_to_marker_steps
import json

# Initialize FastMCP server
mcp = FastMCP("cookidoo-mcp-server")

# Module-level state to store the authenticated session
_cookidoo_service: CookidooService | None = None
_cookidoo_api = None


@mcp.tool()
async def connect_to_cookidoo() -> str:
    """
    Authenticate with Cookidoo and store the session.
    
    This tool must be called before using other Cookidoo tools. It will:
    1. Load your Cookidoo credentials from the .env file
    2. Authenticate with the Cookidoo platform
    3. Store the authenticated session for use by other tools
        
    Returns:
        str: Success message confirming connection
        
    Raises:
        ValueError: If credentials are missing from .env file
        Exception: If authentication fails
    """
    global _cookidoo_service, _cookidoo_api
    
    try:
        # Load credentials from .env file
        email, password = load_cookidoo_credentials()
        
        # Create Cookidoo service instance
        _cookidoo_service = CookidooService(email, password)
        
        # Authenticate and get API client
        _cookidoo_api = await _cookidoo_service.login()
        
        return f"Successfully connected to Cookidoo as {email}"
        
    except ValueError as e:
        # Missing credentials
        return f"Configuration Error: {str(e)}\n\nPlease ensure your .env file contains COOKIDOO_EMAIL and COOKIDOO_PASSWORD"
        
    except Exception as e:
        # Authentication or other errors
        return f"Connection Failed: {str(e)}\n\nPlease check your credentials and try again."


@mcp.tool()
async def get_recipe_details(recipe_id: str) -> str:
    """
    Get detailed information about a specific recipe by its ID.
    
    Use this tool to get full details about a recipe for inspiration before creating
    your own custom recipe. You must be connected first using connect_to_cookidoo.
    
    Args:
        recipe_id: The Cookidoo recipe ID (e.g., "r59322", "r907015")
        
    Returns:
        str: Detailed recipe information including ingredients, steps, cooking time, etc.
        
    Raises:
        Exception: If not connected or if the recipe is not found
    """
    global _cookidoo_api
    
    try:
        # Check if connected
        if not _cookidoo_api:
            return "Not connected. Please run 'connect_to_cookidoo' first."
        
        # Get recipe details
        recipe = await _cookidoo_api.get_recipe_details(recipe_id)
        
        # Format the results
        result = f"Recipe Details:\n\n"
        result += f"Name: {recipe.name}\n"
        result += f"ID: {recipe.id}\n\n"
        
        if hasattr(recipe, 'serving_size'):
            result += f"Servings: {recipe.serving_size}\n"
        
        if hasattr(recipe, 'total_time'):
            result += f"Total Time: {recipe.total_time} minutes\n"
        
        if hasattr(recipe, 'difficulty'):
            result += f"Difficulty: {recipe.difficulty}\n"
        
        result += "\n"
        
        # Ingredients
        if hasattr(recipe, 'ingredients') and recipe.ingredients:
            result += "Ingredients:\n"
            for ingredient in recipe.ingredients:
                if hasattr(ingredient, 'name'):
                    result += f"  • {ingredient.name}"
                    if hasattr(ingredient, 'quantity') and ingredient.quantity:
                        result += f" - {ingredient.quantity}"
                    result += "\n"
            result += "\n"
        
        # Steps
        if hasattr(recipe, 'steps') and recipe.steps:
            result += "Steps:\n"
            for i, step in enumerate(recipe.steps, 1):
                if hasattr(step, 'description'):
                    result += f"{i}. {step.description}\n"
            result += "\n"
        
        # URL if available
        if hasattr(recipe, 'url') and recipe.url:
            result += f"URL: {recipe.url}\n"
        
        return result
        
    except Exception as e:
        return f"Failed to get recipe details: {str(e)}"


@mcp.tool()
async def generate_recipe_structure(
    name: str,
    ingredients: str,
    steps: str,
    servings: int = 4,
    prep_time: int = 30,
    total_time: int = 60,
    hints: str = "",
) -> str:
    """
    Generate and validate a recipe structure ready for upload to Cookidoo.
    
    This tool helps you structure your recipe data properly before uploading.
    It validates all fields and returns a JSON structure that can be used with
    the upload_custom_recipe tool.
    
    Args:
        name: Recipe name (required)
        ingredients: Ingredients list, one per line or comma-separated
        steps: Cooking steps, one per line or numbered
        servings: Number of servings (default: 4, range: 1-20)
        prep_time: Preparation time in minutes (default: 30)
        total_time: Total cooking time in minutes (default: 60)
        hints: Optional cooking tips, one per line or comma-separated
        
    Returns:
        str: Validated recipe structure in JSON format, ready for upload
    """
    try:
        # Parse ingredients (split by newlines or commas)
        ingredients_list = [
            ing.strip() 
            for ing in (ingredients.split('\n') if '\n' in ingredients else ingredients.split(','))
            if ing.strip()
        ]
        
        # Parse steps (split by newlines or numbered steps)
        steps_list = [
            step.strip().lstrip('0123456789.)-• ')
            for step in steps.split('\n')
            if step.strip()
        ]
        
        # Parse hints if provided
        hints_list = None
        if hints:
            hints_list = [
                hint.strip()
                for hint in (hints.split('\n') if '\n' in hints else hints.split(','))
                if hint.strip()
            ]
        
        # Create and validate the recipe using Pydantic
        recipe = CustomRecipe(
            name=name,
            ingredients=ingredients_list,
            steps=steps_list,
            servings=servings,
            prep_time=prep_time,
            total_time=total_time,
            hints=hints_list
        )
        
        # Return formatted JSON
        recipe_json = recipe.model_dump_json(indent=2)
        
        return f"Recipe structure validated successfully!\n\n{recipe_json}\n\nYou can now use this with 'upload_custom_recipe'."
        
    except Exception as e:
        return f"Validation failed: {str(e)}\n\nPlease check your recipe data and try again."


@mcp.tool()
async def upload_custom_recipe(recipe_json: str) -> str:
    """
    Upload a custom recipe to your Cookidoo account.
    
    This tool creates a brand new recipe from scratch on your Cookidoo account.
    Use 'generate_recipe_structure' first to validate your recipe data, then
    pass the resulting JSON to this tool.
    
    Args:
        recipe_json: The validated recipe JSON from generate_recipe_structure
        
    Returns:
        str: Success message with the created recipe ID
    """
    global _cookidoo_service, _cookidoo_api
    
    try:
        # Check if connected
        if not _cookidoo_service or not _cookidoo_api:
            return "Not connected. Please run 'connect_to_cookidoo' first."
        
        # Parse and validate the recipe JSON
        try:
            recipe_data = json.loads(recipe_json)
            recipe = CustomRecipe(**recipe_data)
        except json.JSONDecodeError as e:
            return f"Invalid JSON: {str(e)}"
        except Exception as e:
            return f"Invalid recipe data: {str(e)}"
        
        # Create the recipe using our custom service method
        recipe_id = await _cookidoo_service.create_custom_recipe(
            name=recipe.name,
            ingredients=recipe.ingredients,
            steps=recipe.steps,
            servings=recipe.servings,
            prep_time=recipe.prep_time,
            total_time=recipe.total_time,
            hints=recipe.hints,
        )
        
        # Get localization for URL
        localization = _cookidoo_api.localization
        recipe_url = f"https://{localization.url}/recipes/custom-recipes/{recipe_id}"
        
        return f"Recipe '{recipe.name}' created successfully!\n\nRecipe ID: {recipe_id}\nURL: {recipe_url}\n\nYour recipe is now saved in your Cookidoo account!"
        
    except Exception as e:
        return f"Upload failed: {str(e)}"


@mcp.tool()
async def list_custom_recipes() -> str:
    """
    List your custom recipes stored in Cookidoo.

    This tool scrapes the \"created recipes\" page using your browser cookie
    (COOKIDOO_COOKIE in .env) and returns a JSON list of recipes with:
      - id
      - name
      - url

    You must be connected first using connect_to_cookidoo.
    """
    global _cookidoo_service, _cookidoo_api

    try:
        if not _cookidoo_service or not _cookidoo_api:
            return "Not connected. Please run 'connect_to_cookidoo' first."

        recipes = await _cookidoo_service.list_custom_recipes()
        return json.dumps(recipes, indent=2, ensure_ascii=False)

    except Exception as e:
        return f"Failed to list custom recipes: {str(e)}"


@mcp.tool()
async def update_custom_recipe(recipe_id: str, recipe_json: str) -> str:
    """
    Update an existing custom recipe on Cookidoo.

    This tool works similarly to upload_custom_recipe, but instead of creating
    a new recipe it updates an existing one identified by recipe_id.

    Workflow:
      1. Generate a new recipe structure with generate_recipe_structure
         (or use an edited JSON structure).
      2. Show it to the user for confirmation.
      3. After explicit approval, call update_custom_recipe with:
           - recipe_id: ID from list_custom_recipes
           - recipe_json: the validated JSON to apply.
    """
    global _cookidoo_service, _cookidoo_api

    try:
        if not _cookidoo_service or not _cookidoo_api:
            return "Not connected. Please run 'connect_to_cookidoo' first."

        # Parse and validate the incoming JSON using the same schema
        try:
            data = json.loads(recipe_json)
            recipe = CustomRecipe(**data)
        except json.JSONDecodeError as e:
            return f"Invalid JSON: {str(e)}"
        except Exception as e:
            return f"Invalid recipe data: {str(e)}"

        # Map our validated structure into the low-level Cookidoo payload
        update_data = {
            "name": recipe.name,
            "image": None,
            "isImageOwnedByUser": False,
            "tools": ["TM6"],
            "yield": {"value": recipe.servings, "unitText": "portion"},
            "prepTime": recipe.prep_time * 60,
            "cookTime": 0,
            "totalTime": recipe.total_time * 60,
            "ingredients": [
                {"type": "INGREDIENT", "text": ing} for ing in recipe.ingredients
            ],
            # For updates we currently keep steps as plain STEP instructions.
            # If you want to support [[ACTION:...]] / [[INGREDIENT:...]] in updates
            # as well, we can later introduce the same annotation builder here.
            "instructions": [{"type": "STEP", "text": step} for step in recipe.steps],
            "hints": (
                "\n".join(recipe.hints)
                if recipe.hints and isinstance(recipe.hints, list)
                else (recipe.hints if recipe.hints else "")
            ),
            "workStatus": "PRIVATE",
            "recipeMetadata": {
                "requiresAnnotationsCheck": False,
            },
        }

        await _cookidoo_service.update_custom_recipe(recipe_id, update_data)

        return (
            "Recipe updated successfully!\n\n"
            f"Recipe ID: {recipe_id}\n"
            "You can open the recipe on Cookidoo to verify the changes."
        )

    except Exception as e:
        return f"Update failed: {str(e)}"


@mcp.tool()
async def read_recipe(recipe_id: str) -> str:
    """
    Read a custom recipe by ID and translate its instructions back into
    the marker-based language with [[ACTION:...]] and [[INGREDIENT:...]].

    Returns a JSON string with at least:
      - id
      - name
      - ingredients: list of ingredient texts
      - steps: list of steps using the marker language
    """
    global _cookidoo_service, _cookidoo_api

    try:
        if not _cookidoo_service or not _cookidoo_api:
            return "Not connected. Please run 'connect_to_cookidoo' first."

        raw = await _cookidoo_service.get_custom_recipe(recipe_id)

        # Name can live either at top level or inside recipeContent
        recipe_content = raw.get("recipeContent") or {}
        name = raw.get("name") or raw.get("recipeName") or recipe_content.get("name") or ""

        # Ingredients can be in low-level API format or as a simple list of strings
        ingredients: list[str] = []
        if "ingredients" in raw:
            for ing in raw.get("ingredients", []):
                if isinstance(ing, dict) and ing.get("type") == "INGREDIENT":
                    text = ing.get("text")
                    if text:
                        ingredients.append(text)
        else:
            # Fallback to recipeContent.recipeIngredient (list of strings)
            for text in recipe_content.get("recipeIngredient", []) or []:
                if isinstance(text, str) and text.strip():
                    ingredients.append(text.strip())

        # Instructions: prefer structured form with annotations if present,
        # otherwise fall back to recipeInstructions text list.
        if "instructions" in raw:
            instructions = raw.get("instructions") or []
            steps = instructions_to_steps(instructions)
        else:
            steps_plain = []
            for s in recipe_content.get("recipeInstructions", []) or []:
                if isinstance(s, str) and s.strip():
                    steps_plain.append(s.strip())
            # Best-effort: convert timing fragments like '7 min/120°C/vitesse 1/sens inverse'
            # into [[ACTION:...]] markers.
            steps = text_steps_to_marker_steps(steps_plain)

        result = {
            "id": recipe_id,
            "name": name,
            "ingredients": ingredients,
            "steps": steps,
        }

        return json.dumps(result, indent=2, ensure_ascii=False)

    except Exception as e:
        return f"Failed to read recipe: {str(e)}"

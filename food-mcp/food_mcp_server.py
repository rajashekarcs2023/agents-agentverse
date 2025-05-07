# food_mcp_server.py
from mcp.server.fastmcp import FastMCP
import random

# Create an MCP server named "food"
mcp = FastMCP("food")

@mcp.tool()
async def search_products(query: str) -> str:
    """Search for food products by name, brand, or category
    
    Args:
        query: Search query for food products
    """
    # Mock implementation with common foods
    food_database = {
        "cereal": ["Cheerios", "Corn Flakes", "Granola", "Oatmeal", "Frosted Flakes"],
        "milk": ["Whole Milk", "Skim Milk", "Almond Milk", "Soy Milk", "Oat Milk"],
        "fruit": ["Apple", "Banana", "Orange", "Strawberry", "Blueberry"],
        "vegetable": ["Broccoli", "Carrot", "Spinach", "Tomato", "Cucumber"],
        "meat": ["Chicken Breast", "Ground Beef", "Salmon", "Pork Chop", "Turkey"],
        "yogurt": ["Greek Yogurt", "Low-fat Yogurt", "Strawberry Yogurt", "Vanilla Yogurt"],
        "bread": ["White Bread", "Whole Wheat Bread", "Sourdough", "Baguette", "Ciabatta"],
        "chocolate": ["Dark Chocolate", "Milk Chocolate", "White Chocolate", "Chocolate Bar", "Nutella"],
    }
    
    # Search for matching products
    results = []
    query = query.lower()
    
    # Break query into words for better matching
    query_words = query.split()
    
    # Check for category matches with any word
    for word in query_words:
        if word in food_database:
            results.extend(food_database[word])
    
    # If no results found, try partial matches
    if not results:
        for word in query_words:
            for category, products in food_database.items():
                # Check if query word is in category
                if word in category:
                    results.extend(products)
                else:
                    # Check if query word is in any product
                    for product in products:
                        if word in product.lower():
                            results.append(product)
    
    # Remove duplicates
    results = list(set(results))
    
    if not results:
        return "No food products found matching your query."
    
    # Format the results
    output = f"Found {len(results)} products matching '{query}':\n\n"
    for i, product in enumerate(results, 1):
        output += f"{i}. {product}\n"
    
    return output

@mcp.tool()
async def get_nutrition_facts(product_name: str) -> str:
    """Get detailed nutrition facts for a specific food product
    
    Args:
        product_name: Name of the food product
    """
    # Mock nutrition database with common foods
    nutrition_database = {
        "apple": {
            "calories": 95,
            "fat": 0.3,
            "carbs": 25.1,
            "protein": 0.5,
            "fiber": 4.4,
            "sugar": 19.0,
        },
        "banana": {
            "calories": 105,
            "fat": 0.4,
            "carbs": 27.0,
            "protein": 1.3,
            "fiber": 3.1,
            "sugar": 14.4,
        },
        "chicken breast": {
            "calories": 165,
            "fat": 3.6,
            "carbs": 0.0,
            "protein": 31.0,
            "fiber": 0.0,
            "sugar": 0.0,
        },
        "whole milk": {
            "calories": 149,
            "fat": 7.9,
            "carbs": 12.8,
            "protein": 7.7,
            "fiber": 0.0,
            "sugar": 12.8,
        },
        "broccoli": {
            "calories": 55,
            "fat": 0.6,
            "carbs": 11.2,
            "protein": 3.7,
            "fiber": 5.1,
            "sugar": 2.6,
        },
        "chocolate": {
            "calories": 546,
            "fat": 31.3,
            "carbs": 59.4,
            "protein": 4.9,
            "fiber": 7.0,
            "sugar": 47.5,
        },
        "bread": {
            "calories": 265,
            "fat": 3.2,
            "carbs": 49.0,
            "protein": 9.0,
            "fiber": 2.7,
            "sugar": 5.0,
        },
        "yogurt": {
            "calories": 150,
            "fat": 8.0,
            "carbs": 11.4,
            "protein": 8.5,
            "fiber": 0.0,
            "sugar": 11.4,
        },
    }
    
    # Normalize the product name
    product_key = product_name.lower()
    
    # Search for an exact match first
    if product_key in nutrition_database:
        nutrition = nutrition_database[product_key]
    else:
        # Try a partial match
        for key in nutrition_database.keys():
            if key in product_key or product_key in key:
                product_key = key
                nutrition = nutrition_database[key]
                break
        else:
            # Generate random nutrition facts if no match
            nutrition = {
                "calories": random.randint(50, 350),
                "fat": round(random.uniform(0, 15), 1),
                "carbs": round(random.uniform(0, 50), 1),
                "protein": round(random.uniform(0, 25), 1),
                "fiber": round(random.uniform(0, 10), 1),
                "sugar": round(random.uniform(0, 20), 1),
            }
    
    # Format the nutrition facts
    output = f"📊 NUTRITION FACTS: {product_name.title()} 📊\n\n"
    output += f"Serving Size: 100g\n\n"
    output += f"Calories: {nutrition['calories']} kcal\n"
    output += f"Total Fat: {nutrition['fat']}g\n"
    output += f"Total Carbohydrates: {nutrition['carbs']}g\n"
    output += f"   Dietary Fiber: {nutrition['fiber']}g\n"
    output += f"   Sugars: {nutrition['sugar']}g\n"
    output += f"Protein: {nutrition['protein']}g\n\n"
    
    # Add a health assessment
    if nutrition['calories'] < 100:
        output += "Health Assessment: Low calorie food, good for weight management.\n"
    elif nutrition['fiber'] > 5:
        output += "Health Assessment: Good source of fiber, supports digestive health.\n"
    elif nutrition['protein'] > 15:
        output += "Health Assessment: Good source of protein, supports muscle maintenance.\n"
    elif nutrition['sugar'] > 15:
        output += "Health Assessment: High in sugar, consume in moderation.\n"
    elif nutrition['fat'] > 10:
        output += "Health Assessment: High in fat, consume in moderation.\n"
    else:
        output += "Health Assessment: Balanced nutritional profile.\n"
    
    return output

@mcp.tool()
async def analyze_ingredients(product_name: str) -> str:
    """Analyze the ingredients in a food product
    
    Args:
        product_name: Name of the food product
    """
    # Mock ingredient database
    ingredient_database = {
        "cereal": ["Whole Grain Wheat", "Sugar", "Salt", "Malt Extract", "Vitamins and Minerals"],
        "milk": ["Milk", "Vitamin D", "Vitamin A Palmitate"],
        "chocolate": ["Cocoa Mass", "Sugar", "Cocoa Butter", "Emulsifiers", "Vanilla Extract"],
        "bread": ["Flour", "Water", "Salt", "Yeast", "Vegetable Oil"],
        "yogurt": ["Milk", "Live Cultures", "Sugar", "Fruit Preparation", "Pectin"],
        "apple": ["100% Apple"],
        "banana": ["100% Banana"],
        "chicken": ["Chicken Meat"],
        "nutella": ["Sugar", "Palm Oil", "Hazelnuts", "Cocoa", "Skim Milk", "Lecithin", "Vanillin"],
    }
    
    # Normalize the product name
    product_key = product_name.lower()
    
    # Find ingredients
    ingredients = []
    additives = []
    
    # Search for partial matches in the database
    for key, ing_list in ingredient_database.items():
        if key in product_key or product_key in key:
            ingredients = ing_list
            break
    
    # If no ingredients found, generate random ones
    if not ingredients:
        possible_ingredients = ["Water", "Sugar", "Salt", "Natural Flavors", "Artificial Flavors", 
                              "Preservatives", "Coloring", "Guar Gum", "Lecithin", "Citric Acid",
                              "Stabilizers", "Modified Starch", "Corn Syrup", "Yeast Extract"]
        ingredients = random.sample(possible_ingredients, random.randint(3, 8))
    
    # Check for additives
    common_additives = ["Preservatives", "Artificial Flavors", "Coloring", "Modified Starch", 
                         "Emulsifiers", "Stabilizers", "Lecithin"]
    additives = [ing for ing in ingredients if ing in common_additives]
    
    # Format the response
    output = f"🔍 INGREDIENT ANALYSIS: {product_name.title()} 🔍\n\n"
    output += "Ingredients:\n"
    for ing in ingredients:
        output += f"- {ing}\n"
    
    output += "\nAnalysis:\n"
    
    if not additives:
        output += "✅ This product contains no common additives\n"
    else:
        output += f"⚠️ This product contains {len(additives)} additives:\n"
        for add in additives:
            output += f"  - {add}\n"
    
    # Add health notes
    if "Sugar" in ingredients:
        output += "⚠️ Contains added sugar\n"
    
    if "Salt" in ingredients:
        output += "⚠️ Contains added salt\n"
    
    if "100% Apple" in ingredients or "100% Banana" in ingredients:
        output += "✅ Natural whole food product\n"
    
    if "Whole Grain" in str(ingredients):
        output += "✅ Contains whole grains\n"
    
    return output

if __name__ == "__main__":
    # Run the MCP server
    mcp.run(transport='stdio')
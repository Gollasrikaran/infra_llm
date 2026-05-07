import os
from workflow import build_graph

app = build_graph()

def main():
    print("=== Image Data Extraction Tool ===")
    print("Upload an image to extract data from charts, graphs, and visual content.\n")
    
    while True:
        image_path = input("Enter image file path (or 'quit' to exit): ").strip()
        
        if image_path.lower() in ['quit', 'exit', 'q']:
            print("Goodbye!")
            break
            
        if not os.path.exists(image_path):
            print(f"Error: File '{image_path}' not found. Please try again.\n")
            continue
            
        try:
            print(f"\nProcessing image: {image_path}")
            
            # Initialize state for the workflow
            state_input = {
                "image_path": image_path,
                "extracted_data": "",
                "error": ""
            }
            
            # Run the workflow
            result = app.invoke(state_input)
            
            # Display results
            if result.get("error"):
                print(f"\nError: {result['error']}")
            else:
                print("\n=== Extracted Data ===")
                print(result.get("extracted_data", "No data extracted"))
            
            print("=" * 30 + "\n")
            
        except Exception as e:
            print(f"Error processing image: {str(e)}\n")

if __name__ == "__main__":
    main()

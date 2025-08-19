# Text to context

import json
import os

file_list = os.listdir('.')

file_list = [x for x in file_list if '.txt' in x]

for file_name in file_list:
    with open(file_name, 'r') as file:
        text = file.read()
    
    for line in text.splitlines():
        message = line.split(':', 1) #  `:` do horario e depois `:` separando nome da conversa
        
        if len(message) < 2: ## continue quando for mensagem do wpp
            continue

        date  = message.split(' – ', 0)

        , value = parts
        key = key.strip()
        value = value.strip()
        
        if 'context' not in locals():
            context = {}
        
        context[key] = value
    output_file_name = file_name.replace('.txt', '.json')
    
    with open(output_file_name, 'w') as output_file:
        json.dump(context, output_file, indent=4)
    
    print(f"Processed {file_name} into {output_file_name}")
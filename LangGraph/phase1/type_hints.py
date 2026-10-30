# We use mypy for type checking in python
# "|" refers to Optional. Optional refers to an argument which can be None. If argument is not passed then by default it will be None
# "->" refers to the return type of the function
'''
 TypeDict is a class that is used to create a dictionary with type hints
 TypedDict allows the users to define a dictionary with type hints
'''
'''
# name: str = "Vardhan"
# age: int = 38

# age = "38"    # Assigning string instead of integer gives us a warning from mypy not error
'''

# we can define like this without Optional: def create_user(first_name: str, last_name: str, age: int | None = None) -> dict:

# Using Optional
'''
from typing import TypedDict, Optional

def create_user(first_name: str, last_name: str, age: Optional[int] = None) -> dict:
    email = f"{first_name.lower()}.{last_name.lower()}@example.com"
    return {
        "first_name":first_name,
        "last_name":last_name,
        "email": email,
        "age": age,
    }
'''

'''
dict[str, str | int | None] -> it refers to the dict which has a structure like {key, value}
So it refers to the output where the key can be only "str" data type but the value can be either "str" or "int" or "None"
'''
'''
def create_user(first_name: str, last_name: str, age: int | None = None) -> dict[str, str | int | None]:
    email = f"{first_name.lower()}.{last_name.lower()}@example.com"
    return {
        "first_name":first_name,
        "last_name":last_name,
        "email": email,
        "age": age,
    }
user1 = create_user("Vardhan", "Chilakamarri", age= 21)
user2 = create_user("Rohith", "Chilakamarri", age= 25)
print(user1)
print(user2)
'''
# ---- Type Aliasing ----

# when the function signature is long and when we have the return type which is same as the input type then we can use type alias

# Example:
 
'''
from typing import Optional
type RGB = tuple[int, int, int] # values regarding the RGB colors
type HSL = tuple[int, int, int] # HSL stands for Hue, Saturation and Lightness

type User = dict[str, str | int | RGB | HSL | None]

def create_user(first_name: str, last_name: str,  age: int | None = None, fav_color: RGB | None = None) -> User:
    email = f"{first_name.lower()}.{last_name.lower()}@example.com"
    return {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "age": age,
        "fav_color": fav_color,  # Mypy now accepts this because RGB is in User type!
    }

user1 = create_user("Vardhan", "Chilakamarri", age=21)
user2 = create_user("Rohith", "Chilakamarri", age=25, fav_color=(255, 0, 0))
user3 = create_user("John", "Doe", fav_color=(120, 120, 120))
print(user1)
print(user2)
print(user3)
'''

# ---- NewType ----

'''
The syntax for NewType is NewType("Name of the new type", type)
It is used to create a distinct type from the given type
This is useful for type checking
'''

'''
from typing import NewType

RGB = NewType("RGB", tuple[int, int, int]) # values regarding the RGB colors
HSL = NewType("HSL", tuple[int, int, int]) # HSL stands for Hue, Saturation and Lightness

type User = dict[str, str | int | RGB | HSL | None]

def create_user(first_name: str, last_name: str,  age: int | None = None, fav_color: RGB | None = None) -> User:
    email = f"{first_name.lower()}.{last_name.lower()}@example.com"
    
    str_age = str(age)

    return {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "age": str_age,
        "fav_color": fav_color,  # Mypy now accepts this because RGB is in User type!
    }

user1 = create_user("Vardhan", "Chilakamarri", age=21)
user2 = create_user("Rohith", "Chilakamarri", age=25, fav_color=RGB((255, 0, 0)))
user3 = create_user("John", "Doe", fav_color=HSL((120, 120, 120)))
print(user1)
print(user2)
print(user3)
'''

# ----- TypedDict -----

'''
TypedDict is used to create a dictionary with type hints
It is used to create a dictionary with type hints
It can also be used with NewType, TypeAlias and can be used as a function
'''
'''
from typing import NewType, TypedDict

RGB = NewType("RGB", tuple[int, int, int]) # values regarding the RGB colors
HSL = NewType("HSL", tuple[int, int, int]) # HSL stands for Hue, Saturation and Lightness

# We create a class named User using by inherting from TypedDict so that we can use this instead of Type Aliasing
# The values in the class are the same as the values in the dictionary
# We can use this type hinting and type checking and autocompletion

class User(TypedDict):
    first_name: str
    last_name: str
    email: str
    age: int | None
    fav_color: RGB | None

def create_user(first_name: str, last_name: str,  age: int | None = None, fav_color: RGB | None = None) -> User:
    email = f"{first_name.lower()}.{last_name.lower()}@example.com"
    
    return {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "age": age,
        "fav_color": fav_color,
    }

user1 = create_user("Vardhan", "Chilakamarri", age=21)
user2 = create_user("Rohith", "Chilakamarri", age=25, fav_color=RGB((255, 0, 0)))
user3 = create_user("John", "Doe", fav_color=HSL((120, 120, 120)))
print(user1)
print(user2)
print(user3)
'''


# ----- dataclass -----
'''
We use dataclass decorator on the top of the class so that we don't have to write the __init__ method
we use dataclass decorator for type hinting
'''

'''
from typing import NewType
from dataclasses import dataclass

RGB = NewType("RGB", tuple[int, int, int]) # values regarding the RGB colors
HSL = NewType("HSL", tuple[int, int, int]) # HSL stands for Hue, Saturation and Lightness

@dataclass 
class User:
    first_name: str
    last_name: str
    email: str
    age: int | None = None
    fav_color: RGB | None = None

def create_user(first_name: str, last_name: str,  age: int | None = None, fav_color: RGB | None = None) -> User:
    email = f"{first_name.lower()}.{last_name.lower()}@example.com"
    
    # We return a User class instead of a dictionary
    return User(
        first_name = first_name,
        last_name = last_name,
        email = email,
        age = age,
        fav_color = fav_color,
    )

user1 = create_user("Vardhan", "Chilakamarri", age = 21)
user2 = create_user("Rohith", "Chilakamarri", age = 25, fav_color = RGB((255, 0, 0)))
user3 = create_user("John", "Doe", fav_color = HSL((120, 120, 120)))
print(user1)
print(user2)
print(user3)
'''

# ----- Generic Types -----

# 1. --------- Any ------------------
'''
We use generic types when we want to create a type that can be used with different types of data
This can be used with different types of data types like list, tuple, dict etc..
'''


# from typing import NewType, Any
# from dataclasses import dataclass
# import random

# RGB = NewType("RGB", tuple[int, int, int]) # values regarding the RGB colors
# HSL = NewType("HSL", tuple[int, int, int]) # HSL stands for Hue, Saturation and Lightness

# @dataclass 
# class User:
#     first_name: str
#     last_name: str
#     email: str
#     age: int | None = None
#     fav_color: RGB | None = None

# def create_user(first_name: str, last_name: str,  age: int | None = None, fav_color: RGB | None = None) -> User:
#     email = f"{first_name.lower()}.{last_name.lower()}@example.com"
    
#     # We return a User class instead of a dictionary
#     return User(
#         first_name = first_name,
#         last_name = last_name,
#         email = email,
#         age = age,
#         fav_color = fav_color,
#     )

# # def random_choice(items: list[User]) -> User: # it indicates that the items are a list of users and we return a user
# #     return random.choice(items)

# '''
# When we use Any as type hint, it indicates that the items are of any type and we return a value of any type
# This is useful when we want to create a type that can be used with different types of data
# This is also useful when we want to create a type that can be used with different types of data types like list, tuple, dict etc..
# '''
# def random_choice(items: list[Any]) -> Any: # it indicates that this function can be used with different types of data types like list, tuple, dict etc..
#     return random.choice(items)

# user1 = create_user("Vardhan", "Chilakamarri", age = 21)
# user2 = create_user("Rohith", "Chilakamarri", age = 25, fav_color = RGB((255, 0, 0)))
# user3 = create_user("John", "Doe", fav_color = HSL((120, 120, 120)))


# users = [user1, user2, user3]
# rando_user = random_choice(users)
# print(rando_user)

# emails = [user.email for user in users]
# rando_email = random.choice(emails)
# print(rando_email)




# 2. --------- TypeVars --------------

'''
TypeVar is used to create a type variable that can be used to represent any type
This is useful when we want to create a type that can be used with different types of data
This is also useful when we want to create a type that can be used with different types of data types like list, tuple, dict etc..
'''

'''
from typing import NewType, TypeVar
from dataclasses import dataclass
import random

RGB = NewType("RGB", tuple[int, int, int]) # values regarding the RGB colors
HSL = NewType("HSL", tuple[int, int, int]) # HSL stands for Hue, Saturation and Lightness
type Color = RGB | HSL

@dataclass 
class User:
    first_name: str
    last_name: str
    email: str
    age: int | None = None
    fav_color: Color | None = None

def create_user(first_name: str, last_name: str,  age: int | None = None, fav_color: RGB | None = None) -> User:
    email = f"{first_name.lower()}.{last_name.lower()}@example.com"
    
    # We return a User class instead of a dictionary
    return User(
        first_name = first_name,
        last_name = last_name,
        email = email,
        age = age,
        fav_color = fav_color,
    )

# method-1
# T = TypeVar("T") # This is a type variable that can be used to represent any type
# def random_choice(items: list[T]) -> T: # it indicates that we can take a list of any type and return the same type of element from list. Like if we give a list of strings, it returns a string
#     return random.choice(items)

# method-2
def random_choice[T](items: list[T]) -> T:
    return random.choice(items)

user1 = create_user("Vardhan", "Chilakamarri", age = 21)
user2 = create_user("Rohith", "Chilakamarri", age = 25, fav_color = RGB((255, 0, 0)))
user3 = create_user("John", "Doe", fav_color = HSL((120, 120, 120)))


users = [user1, user2, user3]
rando_user = random_choice(users)
print(rando_user)

emails = [user.email for user in users]
rando_email = random.choice(emails)
print(rando_email)

'''


from typing import NewType
import random
from dataclasses import dataclass
import requests

resp = requests.get("https://coreyms.com", timeout = 5)
status = resp.status_code


RGB = NewType("RGB", tuple[int, int, int]) # values regarding the RGB colors
HSL = NewType("HSL", tuple[int, int, int]) # HSL stands for Hue, Saturation and Lightness
Color = RGB | HSL

@dataclass 
class User:
    first_name: str
    last_name: str
    email: str
    age: int | None = None
    fav_color: RGB | None = None

def create_user(first_name: str, last_name: str,  age: int | None = None, fav_color: RGB | None = None) -> User:
    email = f"{first_name.lower()}.{last_name.lower()}@example.com"
    
    # We return a User class instead of a dictionary
    return User(
        first_name = first_name,
        last_name = last_name,
        email = email,
        age = age,
        fav_color = fav_color,
    )

from typing import TypeVar

T = TypeVar("T")

# Python 3.10/3.11 compatible syntax (or use Python 3.12+ PEP 695: def random_choice[T](...))
def random_choice(items: list[T]) -> T:
    return random.choice(items)

user1 = create_user("Vardhan", "Chilakamarri", age = 21)
user2 = create_user("Rohith", "Chilakamarri", age = 25, fav_color = RGB((255, 0, 0)))
user3 = create_user("John", "Doe", fav_color = HSL((120, 120, 120)))

users = [user1, user2, user3]
rando_user = random_choice(users)
print(rando_user)

emails = [user.email for user in users]
rando_email = random.choice(emails)
print(rando_email)

# The inputs must be as Generic as possible and the output must be Specific 


# ----- Literal Types -----
'''
Literal is used when a variable, argument, or return value must be EXACTLY one of a specific set of predefined literal values (e.g. specific strings or ints).
Unlike general types like `str`, `Literal["admin", "user"]` restricts values to ONLY those exact strings.
This is heavily used in AI agent workflows (like LangGraph) for conditional routing between nodes.
'''

from typing import Literal

UserRole = Literal["admin", "user", "guest"]
AccountStatus = Literal["active", "pending", "suspended"]

@dataclass 
class UserWithRole:
    first_name: str
    last_name: str
    email: str
    role: UserRole = "user"
    status: AccountStatus = "active"
    age: int | None = None
    fav_color: RGB | None = None

def get_user_permissions(role: UserRole) -> list[str]:
    if role == "admin":
        return ["create", "read", "update", "delete"]
    elif role == "user":
        return ["read", "update"]
    else:
        return ["read"]

user_admin = UserWithRole("Vardhan", "Chilakamarri", "vardhan@example.com", role="admin", status="active")
user_guest = UserWithRole("John", "Doe", "john@example.com", role="guest", status="pending")

print(user_admin)
print(f"Admin permissions: {get_user_permissions(user_admin.role)}")
print(f"Guest permissions: {get_user_permissions(user_guest.role)}")
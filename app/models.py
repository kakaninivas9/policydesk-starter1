"""SQLModel tables and API schemas for PolicyDesk.

Four tables so far: Customer, Product, Quote, Policy.
Flow: Customer + Product -> Quote -> Policy -> Claim
"""

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import EmailStr
from sqlmodel import Field, Relationship, SQLModel


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class ProductCode(str, Enum):
    HEALTH = "HEALTH"
    MOTOR = "MOTOR"
    TERM_LIFE = "TERM_LIFE"


class PolicyStatus(str, Enum):
    ACTIVE = "Active"
    LAPSED = "Lapsed"
    CANCELLED = "Cancelled"


class ClaimStatus(str, Enum):
    FILED = "Filed"
    UNDER_REVIEW = "Under Review"
    APPROVED = "Approved"
    REJECTED = "Rejected"


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------
class CustomerBase(SQLModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr = Field(index=True)
    phone: str = Field(min_length=10, max_length=15)
    date_of_birth: date


class Customer(CustomerBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    quotes: list["Quote"] = Relationship(back_populates="customer")
    policies: list["Policy"] = Relationship(back_populates="customer")


class CustomerCreate(CustomerBase):
    pass


class CustomerRead(CustomerBase):
    id: int
    created_at: datetime


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------
class ProductBase(SQLModel):
    code: ProductCode = Field(unique=True, index=True)
    name: str
    description: str = ""
    base_rate: float = Field(
        gt=0,
        description="Premium per rupee of sum insured per year",
    )
    min_sum_insured: float = Field(gt=0)
    max_sum_insured: float = Field(gt=0)


class Product(ProductBase, table=True):
    id: int | None = Field(default=None, primary_key=True)


class ProductRead(ProductBase):
    id: int


# ---------------------------------------------------------------------------
# Quote
# ---------------------------------------------------------------------------
class QuoteBase(SQLModel):
    customer_id: int = Field(foreign_key="customer.id")
    product_id: int = Field(foreign_key="product.id")
    sum_insured: float = Field(gt=0)
    tenure_years: int = Field(ge=1, le=3)
    add_ons: str = Field(
        default="",
        description="Comma-separated add-on codes, e.g. CRITICAL_ILLNESS",
    )


class Quote(QuoteBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    premium: float
    created_at: datetime = Field(default_factory=datetime.utcnow)

    customer: Customer = Relationship(back_populates="quotes")
    product: Product = Relationship()
    policy: Optional["Policy"] = Relationship(back_populates="quote")


class QuoteCreate(QuoteBase):
    pass


class QuoteRead(QuoteBase):
    id: int
    premium: float
    created_at: datetime


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------
class PolicyBase(SQLModel):
    quote_id: int = Field(foreign_key="quote.id", unique=True)
    start_date: date


class Policy(PolicyBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    policy_number: str = Field(unique=True, index=True)
    customer_id: int = Field(foreign_key="customer.id")
    product_id: int = Field(foreign_key="product.id")
    sum_insured: float
    premium: float
    end_date: date
    status: PolicyStatus = Field(default=PolicyStatus.ACTIVE)
    vehicle_registration: str | None = Field(
        default=None,
        description="Motor policies only",
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)

    quote: Quote = Relationship(back_populates="policy")
    customer: Customer = Relationship(back_populates="policies")
    product: Product = Relationship()
    claims: list["Claim"] = Relationship(back_populates="policy")


class PolicyCreate(PolicyBase):
    vehicle_registration: str | None = None


class PolicyRead(SQLModel):
    id: int
    policy_number: str
    quote_id: int
    customer_id: int
    product_id: int
    sum_insured: float
    premium: float
    start_date: date
    end_date: date
    status: PolicyStatus
    vehicle_registration: str | None
    created_at: datetime


class PolicyStatusUpdate(SQLModel):
    status: PolicyStatus


# ---------------------------------------------------------------------------
# Claim
# ---------------------------------------------------------------------------
class ClaimBase(SQLModel):
    policy_id: int = Field(foreign_key="policy.id")
    amount: float = Field(gt=0)
    description: str = Field(min_length=5, max_length=500)
    incident_date: date
    vehicle_registration: str | None = Field(
        default=None,
        description="Required for Motor claims",
    )


class Claim(ClaimBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    status: ClaimStatus = Field(default=ClaimStatus.FILED)
    reason: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    policy: "Policy" = Relationship(back_populates="claims")


class ClaimCreate(ClaimBase):
    pass


class ClaimRead(ClaimBase):
    id: int
    status: ClaimStatus
    reason: str | None
    created_at: datetime


class ClaimStatusUpdate(SQLModel):
    status: ClaimStatus
    reason: str | None = None
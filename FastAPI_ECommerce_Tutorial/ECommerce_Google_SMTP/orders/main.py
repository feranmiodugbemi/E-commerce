from fastapi import APIRouter, Request, Depends, Form, status, BackgroundTasks
from pydantic import EmailStr
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from cart.cart import Cart
from dependencies import get_db, templates, env
from orders import crud
from orders.mail import Mail
from payment.crud import payment_process
from shop.models import Product
from shop.recommender import Recommender

router= APIRouter(
    prefix="/order"
)

@router.get("/create_order")
def order_add(request: Request, db:Session= Depends(get_db)):

    cart= Cart(request,db)
    template= env.get_template('order.html')

    return templates.TemplateResponse(template, {"request": request,
                                                     "cart": cart})

@router.post("/create_order")
def order_add(background_tasks: BackgroundTasks,
                    request: Request,
                    db: Session= Depends(get_db),
                  first_name: str= Form(...),
                  last_name: str= Form(...),
                  email: EmailStr= Form(...),
                  address: str= Form(...),
                  postal_code: int= Form(...),
                  city: str= Form(...)):

    cart= Cart(request,db)

    recommender= Recommender()

    db_order= crud.create_order(db,first_name,last_name,email,address,postal_code,city,
                                cart.coupon_id, cart.get_discount())
    order_id= db_order.id
    request.session['order_id']= order_id

    total_price= cart.get_total_price_after_discount()
    payment_session=payment_process(total_price)

    recommending= []
    for item in cart:
        product_id= item["product"]["id"]
        crud.create_order_item(item,order_id,product_id,db)

        recommending.append(db.query(Product).filter(Product.id== product_id).first())

    cart.remove_all()

    mail= Mail()
    background_tasks.add_task(mail.send_notification)

    recommender.products_bought(recommending)

    return RedirectResponse(url=payment_session.url, status_code=status.HTTP_303_SEE_OTHER)

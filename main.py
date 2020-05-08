from data.forms import RegistrationForm, LoginForm, AddProductForm, AuctionForm, SearchForm, BuyForm
from flask_login import login_user, logout_user, current_user, LoginManager, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from data import db_session, Users, Products, Auctions, Deals
from data.forms import DealForm, CloseForm, AcceptForm
from flask import Flask, render_template, redirect
from random import choice, randint
import datetime


def my_hash(s):
    data_p = [10 ** 9 + 7, 10 ** 9 + 9, 998244353]
    data_step = [239, 713, 53]
    p = choice(data_p)
    step = choice(data_step)
    added = randint(0, 100)
    rez = ord(s[0]) + added
    for i in range(1, len(s)):
        rez = (rez * step + ord(s[i]) + added) % p
    return rez


app = Flask(__name__)
f = open('Config.txt')
app.config["SECRET_KEY"] = str(my_hash(f.readline()))
app.config["UPLOAD_FOLDER"] = "static/image/users"
login_manager = LoginManager()
login_manager.init_app(app)


@app.route("/")
@app.route("/index")
def index():
    session = db_session.create_session()
    return render_template("index.html", current_user=current_user, session=session,
                           Product=Products.Product)


@app.route("/accept_deal/<int:deal_id>", methods=["GET", "POST"])
@login_required
def accept_deal(deal_id):
    # id сделки
    form = AcceptForm()
    session = db_session.create_session()
    deal = session.query(Deals.Deal).get(deal_id)
    prod = session.query(Products.Product).get(deal.product)
    from_user = session.query(Users.User).get(int(deal.participants.split(';')[0]))
    to_user = session.query(Users.User).get(int(deal.participants.split(';')[1]))
    if from_user.id != current_user.id:
        return render_template("no_access.html")
    if form.yes.data:
        deal.date = datetime.datetime.now()
        prod.owner = to_user.id
        to_user.products = ';'.join(to_user.products.split(';') + [str(prod.id)])
        from_user.money += int(deal.history)
        from_user.products = ';'.join(list(filter(
            lambda x: int(x) != prod.id, from_user.products.split(';'))))
        prod.is_sold = True
        session.commit()
        return redirect("/")
    if form.no.data:
        to_user.money += int(deal.history)
        from_user.deals = ';'.join(list(filter(lambda x: int(x) != deal_id, from_user.deals.split(';'))))
        to_user.deals = ';'.join(list(filter(lambda x: int(x) != deal_id, to_user.deals.split(';'))))
        session.delete(deal)
        session.commit()
        return redirect("/")
    return render_template("accept_deal.html", message='', current_user=current_user, form=form,
                           product=prod, money=int(deal.history))


@app.route("/account")
@login_required
def account():
    session = db_session.create_session()
    deals = []
    if current_user.deals is not None and current_user.deals.strip() != "":
        for deal in current_user.deals.split(";"):
            deal = session.query(Deals.Deal).filter(Deals.Deal.id == deal).first()
            curr = session.query(Products.Product).filter(
                Products.Product.id == deal.product).first()
            title = curr.title
            if len(title) > 25:
                title = title[0:24] + "..."
            if deal.participants.split(";")[0] != current_user:
                partner = deal.participants.split(";")[0]
            else:
                partner = deal.participants.split(";")[1]
            user = session.query(Users.User).filter(Users.User.id == partner).first()
            check = "Подтверждено" if curr.is_sold else "Не подтверждено"
            deals += [[deal.product, title, user.name, user.surname, deal.date, check]]
    return render_template("account.html", current_user=current_user, session=session,
                           Product=Products.Product, Deal=Deals.Deal, User=Users.User,
                           account=current_user, enumerate=enumerate, deals=deals)


@app.route("/account/<int:acc_id>")
def account_user(acc_id):
    session = db_session.create_session()
    user = session.query(Users.User).get(acc_id)
    if user is None:
        return redirect("/")
    if current_user.is_authenticated:
        if acc_id == current_user.id:
            return redirect("/account")
    return render_template("user.html", session=session, user=user, Product=Products.Product)


@app.route("/add_product", methods=["GET", "POST"])
@login_required
def add_product():
    form = AddProductForm()
    if form.validate_on_submit():
        session = db_session.create_session()
        photo = form.photo.data
        product_to_add = Products.Product()
        product_to_add.title = form.title.data
        product_to_add.description = form.description.data
        product_to_add.owner = current_user.id
        product_to_add.lower = product_to_add.title.lower()
        session.add(product_to_add)
        session.commit()
        products = session.query(Products.Product).all()
        products = map(lambda x: x.id, products)
        products = str(max(products))
        photo.save(f"static/image/products/{products}.jpg")
        user = session.query(Users.User).filter(current_user.id == Users.User.id).first()
        if user.products:
            user.products += '; ' + products
        else:
            user.products += products
        session.commit()
        return redirect("/account")
    return render_template("AddProduct.html", message="", current_user=current_user, form=form)


@app.route("/buy/<int:product_id>", methods=["GET", "POST"])
@login_required
def buy(product_id):
    # id продукта
    # try:
    form = BuyForm()
    session = db_session.create_session()
    auc = session.query(Auctions.Auction).filter(Auctions.Auction.product == product_id).first()
    pr = session.query(Products.Product).filter(Products.Product.id == product_id)[0]
    user = session.query(Users.User).filter(Users.User.id == current_user.id)[0]
    history = auc.history.split(';')
    cost = int(history[-1])
    if form.validate_on_submit():
        money = current_user.money
        if not (form.cost.data > money or form.cost.data < cost + 15):
            auc.history = ";".join(history + [str(form.cost.data)])
            user.money -= form.cost.data
            try:
                last_user = session.query(Users.User).filter(
                    Users.User.id == int(auc.participants.split(';')[-1]))[0]
                last_user.money += int(auc.history.split(';')[-1])
            except Exception as error:
                print(error)
            auc.participants = ';'.join(
                [i for i in auc.participants.split(";") + [str(current_user.id)] if i.strip() != ""])
            session.commit()
            return redirect("/")
        if form.cost.data < cost + 15:
            return render_template("buy.html",
                                   message='Увеличте предыдущую ставку хотя бы на 15 у.е.',
                                   current_user=current_user, form=form, cost=cost, product=pr)
        return render_template("buy.html", message='Не хватает денег', current_user=current_user,
                               form=form,
                               cost=cost, product=pr)
    return render_template("buy.html", message='', current_user=current_user, form=form, cost=cost,
                           product=pr)
    # except Exception as e:
    #     return redirect("/")


@app.route("/close_auction/<int:auc_id>", methods=["GET", "POST"])
@login_required
def close_auction(auc_id):
    # id аукциона
    form = CloseForm()
    session = db_session.create_session()
    auc = session.query(Auctions.Auction).filter(Auctions.Auction.id == auc_id)[0]
    prod = session.query(Products.Product).filter(Products.Product.id == auc.product)[0]
    last = auc.participants.split(';')[-1]
    win = session.query(Users.User).filter(Users.User.id == last)[0]
    win_money = int(auc.history.split(';')[-1])
    user = session.query(Users.User).filter(Users.User.id == current_user.id)[0]
    if form.submit.data and prod.owner == user.id:
        prod.owner = last
        win.products = ';'.join(win.products.split(';') + [str(prod.id)])
        auc.winner = last
        user.money += win_money
        deal = Deals.Deal()
        deal.participants = ';'.join([str(current_user.id), str(last)])
        deal.product = prod.id
        deal.histaory = win_money
        deal.date = datetime.datetime.now()
        auc.deal = deal.id
        session.add(deal)
        user.deal = ';'.join(user.deal.split(';') + [str(deal.id)])
        win.deal = ';'.join(win.deal.split(';') + [str(deal.id)])
        session.delete(auc)
        session.commit()
        return redirect("/")
    if form.submit.data:
        return render_template("no_access.html")
    return render_template("close_auction.html", message='', current_user=current_user, form=form,
                           product=prod, money=win_money)


@app.route("/inventory")
@login_required
def inventory():
    session = db_session.create_session()
    inv = session.query(Products.Product).filter(Products.Product.owner == current_user.id)
    inv = list(
        map(lambda x: (("static\\image\\products\\" + str(x.id) + ".jpg"), x), inv))
    return render_template('inventory.html', current_user=current_user, inventory=inv)


@login_manager.user_loader
def load_user(user_id):
    session = db_session.create_session()
    return session.query(Users.User).get(user_id)


@app.route("/login", methods=["POST", "GET"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        session = db_session.create_session()
        user = session.query(Users.User).filter(Users.User.email == form.login.data).first()
        if user is None:
            return render_template("login.html", current_user=current_user, form=form,
                                   message="Пользователя с подобной почтой не существует.")
        if check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            return redirect("/")
        return render_template("login.html", current_user=current_user, form=form,
                               message="Ложный пароль.")
    return render_template("login.html", current_user=current_user, form=form, message="")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/")


@app.route("/make_deal/<int:deal_id>", methods=["GET", "POST"])
@login_required
def make_deal(deal_id):
    session = db_session.create_session()
    curr_product = session.query(Products.Product).get(deal_id)
    owner = session.query(Users.User).get(curr_product.owner)
    cur = session.query(Users.User).get(current_user.id)
    form = DealForm()
    if form.validate_on_submit():
        if cur.money >= form.cost.data >= 0:
            deal = Deals.Deal()
            deal.product = curr_product.id
            deal.participants = ';'.join([str(owner.id), str(cur.id)])
            deal.history = str(form.cost.data)
            deal.date = datetime.datetime.now()
            cur.money -= form.cost.data
            session.add(deal)
            session.commit()
            owner.deals = ';'.join(owner.deals.split(';') + [
                str(deal.id)]) if owner.deals else str(deal.id)
            cur.deals = ';'.join(
                cur.deals.split(';') + [str(deal.id)]) if cur.deals else str(deal.id)
            session.commit()
            return redirect(f"/product/{curr_product.id}")
        elif form.cost.data < 0:
            return render_template("Deal.html", form=form, product=curr_product, owner=owner,
                                   message="Это не нефть.")
        else:
            return render_template("Deal.html", form=form, product=curr_product, owner=owner,
                                   message="У вас нет такого числа денег")
    return render_template("Deal.html", form=form, product=curr_product, owner=owner, message="")


@app.route("/new_auction", methods=["GET", "POST"])
@login_required
def new_auction():
    form = AuctionForm()
    if form.search.data and form.product.data:
        session = db_session.create_session()
        good = session.query(Products.Product).filter(
            Products.Product.lower.like(f"%{form.product.data.lower()}%"),
            Products.Product.is_sold == 0)
        inv = list(
            map(lambda x: (("static\\image\\products\\" + str(x.id) + ".jpg"), x), good))
        return render_template("AddAuction.html", message='', current_user=current_user, form=form,
                               inventory=inv)
    if form.submit.data and form.product.data and form.number.data:
        session = db_session.create_session()
        good = session.query(Products.Product).filter(Products.Product.lower.like(
            f"%{form.product.data.lower()}%"), Products.Product.is_sold == 0)
        try:
            auction = Auctions.Auction()
            auction.id = good[form.number.data - 1].id
            auction.product = auction.id
            auction.participants = ""
            auction.history = "0"
            session.add(auction)
            session.commit()
            return redirect("/")
        except Exception as error:
            print(error)
            return render_template("AddAuction.html", message='Введите действительный номер',
                                   current_user=current_user,
                                   form=form, inventory=[])
    return render_template("AddAuction.html", message='', current_user=current_user, form=form,
                           inventory=[])


@app.route("/product/<int:pr_id>")
def product(pr_id):
    session = db_session.create_session()
    pr = session.query(Products.Product).filter(Products.Product.id == pr_id).first()
    if pr is None:
        return redirect("/")
    owner = session.query(Users.User).get(pr.owner)
    return render_template("product.html", product=pr, owner=owner, current_user=current_user)


@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        session = db_session.create_session()
        if form.photo.data:
            filename = form.photo.data.filename
            form.photo.data.save(
                "static/image/users/" + form.login.data + "." + filename.split(".")[-1])
        if session.query(Users.User).filter(Users.User.email == form.login.data).first() is not None:
            return render_template("register.html", message="Подобный email уже используется.",
                                   current_user=current_user, form=form)
        if form.password.data != form.confirm_password.data:
            return render_template("register.html", message="Пароли не совпадают.",
                                   current_user=current_user,
                                   form=form)
        user = Users.User()
        user.email = form.login.data
        user.password = generate_password_hash(form.password.data)
        user.name = form.name.data
        user.surname = form.surname.data
        user.money = 50.0
        user.photo = form.photo.data.filename.split(".")[-1] if form.photo.data else ""
        session.add(user)
        session.commit()
        login_user(user)
        return redirect("/")
    return render_template("register.html", message="", current_user=current_user, form=form)


@app.route("/search", methods=["GET", "POST"])
def search():
    form = SearchForm()
    session = db_session.create_session()
    if form.search.data and form.product.data:
        good = session.query(Products.Product).filter(Products.Product.lower.like(
            f"%{form.product.data.lower()}%"), Products.Product.is_sold == 0)
        inv = list(
            map(lambda x: (("static\\image\\products\\" + str(x.id) + ".jpg"), x), good))
        return render_template("Search.html", message='', current_user=current_user, form=form,
                               inventory=inv)
    if form.submit.data and form.product.data and form.number.data:
        session = db_session.create_session()
        good = session.query(Products.Product).filter(Products.Product.lower.like(
            f"%{form.product.data.lower()}%"), Products.Product.is_sold == 0)
        try:
            return redirect(f"/product/{good[form.number.data - 1].id}")
        except Exception as error:
            print(error)
            return render_template("Search.html", message='Введите действительный номер',
                                   current_user=current_user,
                                   form=form, inventory=[])
    return render_template("Search.html", message='', current_user=current_user, form=form,
                           inventory=[])


if __name__ == "__main__":
    db_session.global_init("db/database.sqlite")
    app.run()

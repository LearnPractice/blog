# coding=utf-8
import  logging
from django.shortcuts import render, redirect, HttpResponse
from django.core.urlresolvers import reverse
from django.conf import settings
from django.contrib.auth import logout, login, authenticate
from django.contrib.auth.hashers import make_password
from django.core.paginator import Paginator,InvalidPage,EmptyPage,PageNotAnInteger
from django.db import connection
from  django.db.models import  Count
from blog.models import *
from forms import *
import json

logger = logging.getLogger('blog.views')
# Create your views here.
def global_settings(request):
    SITE_NAME = settings.SITE_NAME
    SITE_DESC = settings.SITE_DESC
    SITE_COPYRIGHT = settings.SITE_COPYRIGHT

    #分类信息获取（导航数据）
    category_list = Category.objects.all()
    #广告数据
    ad_list = Ad.objects.all()
    #文章归档数据
    archive_list = Article.objects.distinct_date()
    #文章排行数据:评论排行数据
    comment_count_list = Comment.objects.values('article').annotate(comment_count = Count('article')).order_by('-comment_count')
    article_comment_list = [Article.objects.get(pk = comment['article'])for comment in comment_count_list]
    #文章排行数据:浏览量排行
    comment_click_list = Article.objects.all().order_by('-click_count')
    #文章排行数据: 站长推荐排行
    comment_recommemd_list = Article.objects.all().order_by('-is_recommend')
    #标签云数据
    tag_list = Tag.objects.all()
    return  locals()

#实现最新文章数据
def index(request):
    try:
       article_list = getPage( request,Article.objects.all())
    except Exception as e:
        logger.error(e)
    return  render(request, 'index.html',locals())

# 根据标签列出已发布文章
def article_list_by_tag(request, tag):
    articles = Article.objects.annotate(num_comment=Count('comment')).filter(
        date_publish__isnull=False, tags__name=tag).prefetch_related(
        'category').prefetch_related('tags').order_by('-date_publish')
    return render(request, 'article.html',
                  {'posts': articles, 'list_header': '文章标签 \'{}\''.format(tag)})

#实现侧边栏的文章归档
def archive(request):
    try:
        # 先获取客户端提交的信息
        year =request.GET.get('year',None)
        month =request.GET.get('month',None)
        article_list =  Article.objects.filter(date_publish__icontains=year+'-'+month)
        article_list = getPage(request,article_list)
    except Exception as e:
        logger.error(e)
    return  render(request, 'archive.html',locals())

#分页代码
def getPage(request,article_list):
    paginator =  Paginator(article_list,3)
    try:
        page = int(request.GET.get('page',1))
        article_list = paginator.page(page)
    except (InvalidPage,EmptyPage,PageNotAnInteger):
        article_list = paginator.page(1)
    return article_list

# 文章详情
def article(request):
    try:
        # 获取文章id
        id = request.GET.get('id', None)
        try:
            # 获取文章信息
            article = Article.objects.get(pk=id)
        except Article.DoesNotExist:
            return render(request, 'failure.html', {'reason': '没有找到对应的文章'})

        # 评论表单
        comment_form = CommentForm({'author': request.user.username,
                                    'email': request.user.email,
                                    'url': request.user.url,
                                    'article': id} if request.user.is_authenticated() else{'article': id})
        # 获取评论信息
        comments = Comment.objects.filter(article=article).order_by('id')
        comment_list = []
        for comment in comments:
            for item in comment_list:
                if not hasattr(item, 'children_comment'):
                    setattr(item, 'children_comment', [])
                if comment.pid == item:
                    item.children_comment.append(comment)
                    break
            if comment.pid is None:
                comment_list.append(comment)
    except Exception as e:
        print e
        logger.error(e)
    return render(request, 'article.html', locals())

# 提交评论
def comment_post(request):
    try:
        comment_form = CommentForm(request.POST)
        if comment_form.is_valid():
            #获取表单信息
            comment = Comment.objects.create(username=comment_form.cleaned_data["author"],
                                             email=comment_form.cleaned_data["email"],
                                             url=comment_form.cleaned_data["url"],
                                             content=comment_form.cleaned_data["comment"],
                                             article_id=comment_form.cleaned_data["article"],
                                             user=request.user if request.user.is_authenticated() else None)
            comment.save()
        else:
            return render(request, 'failure.html', {'reason': comment_form.errors})
    except Exception as e:
        logger.error(e)
    return redirect(request.META['HTTP_REFERER'])

# 注销
def do_logout(request):
    try:
        logout(request)
    except Exception as e:
        print e
        logger.error(e)
    return redirect(request.META['HTTP_REFERER'])

# 注册
def do_reg(request):
    try:
        if request.method == 'POST':
            reg_form = RegForm(request.POST)
            if reg_form.is_valid():
                # 注册
                user = User.objects.create(username=reg_form.cleaned_data["username"],
                                    email=reg_form.cleaned_data["email"],
                                    url=reg_form.cleaned_data["url"],
                                    password=make_password(reg_form.cleaned_data["password"]),)
                user.save()

                # 登录
                user.backend = 'django.contrib.auth.backends.ModelBackend' # 指定默认的登录验证方式
                login(request, user)
                return redirect(request.POST.get('source_url'))
            else:
                return render(request, 'failure.html', {'reason': reg_form.errors})
        else:
            reg_form = RegForm()
    except Exception as e:
        logger.error(e)
    return render(request, 'reg.html', locals())

# 登录
def do_login(request):
    try:
        if request.method == 'POST':
            login_form = LoginForm(request.POST)
            if login_form.is_valid():
                # 登录
                username = login_form.cleaned_data["username"]
                password = login_form.cleaned_data["password"]
                user = authenticate(username=username, password=password)
                if user is not None:
                    user.backend = 'django.contrib.auth.backends.ModelBackend' # 指定默认的登录验证方式
                    login(request, user)
                else:
                    return render(request, 'failure.html', {'reason': '登录验证失败'})
                return redirect(request.POST.get('source_url'))
            else:
                return render(request, 'failure.html', {'reason': login_form.errors})
        else:
            login_form = LoginForm()
    except Exception as e:
        logger.error(e)
    return render(request, 'login.html', locals())

# 导航中分类信息详情
def category(request):
    try:
        # 先获取客户端提交的信息
        cid = request.GET.get('cid', None)
        try:
            category = Category.objects.get(pk=cid)
        except Category.DoesNotExist:
            return render(request, 'failure.html', {'reason': '分类不存在'})
        article_list = Article.objects.filter(category=category)
        article_list = getPage(request, article_list)
    except Exception as e:
        logger.error(e)
    return render(request, 'category.html', locals())



